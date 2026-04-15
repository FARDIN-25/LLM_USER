from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '84619ddebba5'
down_revision = 'e4bf97772bb9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('profession', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'profession')