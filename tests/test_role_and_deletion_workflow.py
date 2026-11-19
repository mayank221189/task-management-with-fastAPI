import asyncio
import unittest
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import BackgroundTasks
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from src.tasks.task_models import TaskDeletionRequest, TaskModel
from src.user.user_controller import register_user
from src.user.user_dtos import UserBaseSchema
from src.user.user_models import Role, User
from src.utils.db import Base, get_db
from src.utils.settings import settings


class RoleAndDeletionWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

        with self.session_factory.begin() as db:
            db.add_all([Role(name="admin"), Role(name="manager"), Role(name="member")])

        def override_get_db():
            with self.session_factory() as db:
                yield db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.engine.dispose()

    def create_user(
        self, username: str, role_name: str, manager_id: int | None = None
    ) -> int:
        with self.session_factory.begin() as db:
            role = db.scalars(select(Role).where(Role.name == role_name)).one()
            user = User(
                first_name=username,
                last_name="Test",
                username=username,
                hashed_password="not-used",
                email=f"{username}@example.com",
                is_active=True,
                created_at=datetime.now(UTC),
                role=role,
                manager_id=manager_id,
            )
            db.add(user)
            db.flush()
            return user.id

    def create_task(self, assignee_id: int) -> int:
        with self.session_factory.begin() as db:
            task = TaskModel(
                title="Review release",
                description="Prepare the release",
                is_completed=False,
                user_id=assignee_id,
                created_by_id=assignee_id,
            )
            db.add(task)
            db.flush()
            return task.id

    @staticmethod
    def token_for(user_id: int) -> str:
        return jwt.encode(
            {
                "_id": user_id,
                "exp": (datetime.now(UTC) + timedelta(minutes=5)).timestamp(),
            },
            settings.SECRET_KEY,
            settings.ALGORITHM,
        )

    def headers_for(self, user_id: int) -> dict[str, str]:
        return {"Authorization": f"JWT {self.token_for(user_id)}"}

    def test_member_must_request_deletion_and_manager_can_reassign(self) -> None:
        manager_id = self.create_user("manager", "manager")
        member_id = self.create_user("member", "member", manager_id)
        replacement_id = self.create_user("replacement", "member", manager_id)
        other_manager_id = self.create_user("other-manager", "manager")
        outsider_id = self.create_user("outsider", "member", other_manager_id)
        task_id = self.create_task(member_id)

        direct_delete = self.client.delete(
            f"/tasks/task/{task_id}", headers=self.headers_for(member_id)
        )
        self.assertEqual(direct_delete.status_code, 403)

        request = self.client.post(
            f"/tasks/task/{task_id}/deletion-requests",
            headers=self.headers_for(member_id),
            json={"reason": "No longer needed"},
        )
        self.assertEqual(request.status_code, 201)
        request_id = request.json()["id"]

        duplicate = self.client.post(
            f"/tasks/task/{task_id}/deletion-requests",
            headers=self.headers_for(member_id),
            json={},
        )
        self.assertEqual(duplicate.status_code, 409)

        manager_queue = self.client.get(
            "/tasks/deletion-requests", headers=self.headers_for(manager_id)
        )
        self.assertEqual([item["id"] for item in manager_queue.json()], [request_id])
        other_queue = self.client.get(
            "/tasks/deletion-requests", headers=self.headers_for(other_manager_id)
        )
        self.assertEqual(other_queue.json(), [])

        invalid_reassignment = self.client.post(
            f"/tasks/deletion-requests/{request_id}/decision",
            headers=self.headers_for(manager_id),
            json={"decision": "reassign", "assignee_id": outsider_id},
        )
        self.assertEqual(invalid_reassignment.status_code, 400)

        decision = self.client.post(
            f"/tasks/deletion-requests/{request_id}/decision",
            headers=self.headers_for(manager_id),
            json={
                "decision": "reassign",
                "assignee_id": replacement_id,
                "note": "Reassigned to another member",
            },
        )
        self.assertEqual(decision.status_code, 200)
        self.assertEqual(decision.json()["status"], "reassigned")
        self.assertEqual(decision.json()["reassigned_to_id"], replacement_id)

        old_assignee_task = self.client.get(
            f"/tasks/task/{task_id}", headers=self.headers_for(member_id)
        )
        new_assignee_task = self.client.get(
            f"/tasks/task/{task_id}", headers=self.headers_for(replacement_id)
        )
        self.assertEqual(old_assignee_task.status_code, 404)
        self.assertEqual(new_assignee_task.status_code, 200)

    def test_manager_approval_deletes_task_and_preserves_request_audit(self) -> None:
        manager_id = self.create_user("manager", "manager")
        member_id = self.create_user("member", "member", manager_id)
        task_id = self.create_task(member_id)
        request = self.client.post(
            f"/tasks/task/{task_id}/deletion-requests",
            headers=self.headers_for(member_id),
            json={"reason": "Duplicate task"},
        )
        request_id = request.json()["id"]

        decision = self.client.post(
            f"/tasks/deletion-requests/{request_id}/decision",
            headers=self.headers_for(manager_id),
            json={"decision": "approve_delete", "note": "Confirmed duplicate"},
        )

        self.assertEqual(decision.status_code, 200)
        self.assertEqual(decision.json()["status"], "approved")
        self.assertIsNone(decision.json()["task_id"])
        self.assertEqual(decision.json()["original_task_id"], task_id)
        self.assertEqual(
            self.client.get(
                f"/tasks/task/{task_id}", headers=self.headers_for(member_id)
            ).status_code,
            404,
        )
        with self.session_factory() as db:
            saved_request = db.get(TaskDeletionRequest, request_id)
            self.assertIsNotNone(saved_request)
            assert saved_request is not None
            self.assertEqual(saved_request.status, "approved")

    def test_admin_can_assign_a_manager_and_manager_reviews_request(self) -> None:
        admin_id = self.create_user("admin", "admin")
        manager_id = self.create_user("manager", "manager")
        member_id = self.create_user("member", "member")
        task_id = self.create_task(member_id)

        assignment = self.client.patch(
            f"/user/users/{member_id}/access",
            headers=self.headers_for(admin_id),
            json={"manager_id": manager_id},
        )
        self.assertEqual(assignment.status_code, 200)
        self.assertEqual(assignment.json()["manager_id"], manager_id)

        request = self.client.post(
            f"/tasks/task/{task_id}/deletion-requests",
            headers=self.headers_for(member_id),
            json={},
        )
        request_id = request.json()["id"]
        manager_queue = self.client.get(
            "/tasks/deletion-requests", headers=self.headers_for(manager_id)
        )
        self.assertEqual([item["id"] for item in manager_queue.json()], [request_id])

        decision = self.client.post(
            f"/tasks/deletion-requests/{request_id}/decision",
            headers=self.headers_for(manager_id),
            json={"decision": "reject"},
        )
        self.assertEqual(decision.status_code, 200)
        self.assertEqual(decision.json()["status"], "rejected")
        self.assertEqual(
            self.client.get(
                f"/tasks/task/{task_id}", headers=self.headers_for(member_id)
            ).status_code,
            200,
        )

    def test_only_administrators_can_change_access(self) -> None:
        member_id = self.create_user("member", "member")
        other_member_id = self.create_user("other-member", "member")

        response = self.client.patch(
            f"/user/users/{other_member_id}/access",
            headers=self.headers_for(member_id),
            json={"role": "manager"},
        )
        self.assertEqual(response.status_code, 403)

    def test_registration_assigns_member_role(self) -> None:
        with self.session_factory() as db:
            user = asyncio.run(
                register_user(
                    UserBaseSchema(
                        first_name="New",
                        last_name="Member",
                        username="new-member",
                        password="test-password",
                        email="new-member@example.com",
                    ),
                    db,
                    BackgroundTasks(),
                )
            )
            self.assertEqual(user.role.name, "member")
            self.assertIsNone(user.manager_id)

    def test_admin_reviews_requests_from_unmanaged_members(self) -> None:
        admin_id = self.create_user("admin", "admin")
        member_id = self.create_user("member", "member")
        replacement_id = self.create_user("replacement", "member")
        task_id = self.create_task(member_id)
        request = self.client.post(
            f"/tasks/task/{task_id}/deletion-requests",
            headers=self.headers_for(member_id),
            json={},
        )
        request_id = request.json()["id"]

        admin_queue = self.client.get(
            "/tasks/deletion-requests", headers=self.headers_for(admin_id)
        )
        self.assertEqual([item["id"] for item in admin_queue.json()], [request_id])

        decision = self.client.post(
            f"/tasks/deletion-requests/{request_id}/decision",
            headers=self.headers_for(admin_id),
            json={"decision": "reassign", "assignee_id": replacement_id},
        )
        self.assertEqual(decision.status_code, 200)
        self.assertEqual(decision.json()["status"], "reassigned")
        self.assertEqual(
            self.client.get(
                f"/tasks/task/{task_id}", headers=self.headers_for(replacement_id)
            ).status_code,
            200,
        )

    def test_pending_request_moves_to_new_manager(self) -> None:
        admin_id = self.create_user("admin", "admin")
        first_manager_id = self.create_user("manager-one", "manager")
        second_manager_id = self.create_user("manager-two", "manager")
        member_id = self.create_user("member", "member", first_manager_id)
        task_id = self.create_task(member_id)
        request = self.client.post(
            f"/tasks/task/{task_id}/deletion-requests",
            headers=self.headers_for(member_id),
            json={},
        )
        request_id = request.json()["id"]

        reassignment = self.client.patch(
            f"/user/users/{member_id}/access",
            headers=self.headers_for(admin_id),
            json={"manager_id": second_manager_id},
        )
        self.assertEqual(reassignment.status_code, 200)
        first_queue = self.client.get(
            "/tasks/deletion-requests", headers=self.headers_for(first_manager_id)
        )
        second_queue = self.client.get(
            "/tasks/deletion-requests", headers=self.headers_for(second_manager_id)
        )
        self.assertEqual(first_queue.json(), [])
        self.assertEqual([item["id"] for item in second_queue.json()], [request_id])

    def test_manager_hierarchy_cannot_contain_a_cycle(self) -> None:
        admin_id = self.create_user("admin", "admin")
        first_manager_id = self.create_user("manager-one", "manager")
        second_manager_id = self.create_user("manager-two", "manager")
        first_assignment = self.client.patch(
            f"/user/users/{first_manager_id}/access",
            headers=self.headers_for(admin_id),
            json={"manager_id": second_manager_id},
        )
        self.assertEqual(first_assignment.status_code, 200)

        cycle = self.client.patch(
            f"/user/users/{second_manager_id}/access",
            headers=self.headers_for(admin_id),
            json={"manager_id": first_manager_id},
        )
        self.assertEqual(cycle.status_code, 400)

    def test_administrator_can_directly_delete_task(self) -> None:
        admin_id = self.create_user("admin", "admin")
        member_id = self.create_user("member", "member")
        task_id = self.create_task(member_id)
        deletion_request = self.client.post(
            f"/tasks/task/{task_id}/deletion-requests",
            headers=self.headers_for(member_id),
            json={},
        )
        self.assertEqual(deletion_request.status_code, 201)

        response = self.client.delete(
            f"/tasks/task/{task_id}", headers=self.headers_for(admin_id)
        )
        self.assertEqual(response.status_code, 204)
        history = self.client.get(
            "/tasks/deletion-requests?status=rejected",
            headers=self.headers_for(admin_id),
        )
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.json()[0]["status"], "rejected")

    def test_bearer_scheme_is_rejected(self) -> None:
        member_id = self.create_user("member", "member")
        response = self.client.get(
            "/user/is-auth",
            headers={"Authorization": f"Bearer {self.token_for(member_id)}"},
        )
        self.assertEqual(response.status_code, 401)
        jwt_response = self.client.get(
            "/user/is-auth", headers=self.headers_for(member_id)
        )
        self.assertEqual(jwt_response.status_code, 200)
        self.assertEqual(jwt_response.json()["role"]["name"], "member")


if __name__ == "__main__":
    unittest.main()
