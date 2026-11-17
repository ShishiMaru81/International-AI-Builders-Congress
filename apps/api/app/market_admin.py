"""Operator-only provisioning: python -m app.market_admin create-admin --email ... --name ..."""
import argparse
import getpass
import os

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from .db import Session, User, engine, ensure_compat_schema
from .market_auth import hash_password, normalize_email


def create_admin(db: DBSession, *, email: str, name: str, password: str) -> User:
    email = normalize_email(email)
    name = name.strip()
    if not name or len(name) > 120:
        raise ValueError('Name must contain 1 to 120 characters')
    if db.scalar(select(User.id).where(User.email == email)):
        raise ValueError('An account already uses this email; no role was changed')
    user = User(name=name, email=email, password_hash=hash_password(password), role='admin', is_active=True, preferences={})
    try:
        db.add(user)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError('An account already uses this email; no role was changed') from None
    return user


def main():
    parser = argparse.ArgumentParser(description='Provision a marketplace operator account')
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('create-admin')
    create.add_argument('--email', required=True)
    create.add_argument('--name', required=True)
    args = parser.parse_args()
    password = os.environ.get('KRISHIMARKET_ADMIN_PASSWORD')
    if password is None:
        password = getpass.getpass('Admin password (10+ characters): ')
        if password != getpass.getpass('Confirm admin password: '):
            parser.error('Passwords do not match')
    try:
        ensure_compat_schema(engine)
        with Session() as db:
            user = create_admin(db, email=args.email, name=args.name, password=password)
            print(f'Created admin {user.email} ({user.id})')
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
