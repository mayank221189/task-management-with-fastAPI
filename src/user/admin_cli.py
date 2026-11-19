import argparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.user.user_models import Role, User
from src.utils.db import LocalSession


def promote_user_to_admin(username: str, db: Session) -> User:
    user = db.scalars(select(User).where(User.username == username)).one_or_none()
    if user is None:
        raise ValueError(f"No user found with username {username!r}")
    if not user.is_active:
        raise ValueError("An inactive user cannot be promoted to administrator")
    if user.direct_reports:
        raise ValueError("Reassign this user's reports before promoting them")

    administrator_role = db.scalars(
        select(Role).where(Role.name == "admin")
    ).one_or_none()
    if administrator_role is None:
        raise ValueError("Administrator role is missing; run database migrations first")

    user.role = administrator_role
    user.manager_id = None
    return user


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Promote an existing user to the initial administrator."
    )
    parser.add_argument("username", help="Username of the existing user to promote")
    arguments = parser.parse_args()

    try:
        with LocalSession.begin() as db:
            promote_user_to_admin(arguments.username, db)
    except ValueError as error:
        parser.error(str(error))

    print(f"Promoted {arguments.username!r} to administrator.")


if __name__ == "__main__":
    main()
