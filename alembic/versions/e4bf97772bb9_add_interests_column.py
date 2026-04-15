from alembic import op
import sqlalchemy as sa

revision = 'e4bf97772bb9'
down_revision = '112a06d3e7a8'


def upgrade() -> None:
    op.add_column('users', sa.Column('interests', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'interests')

