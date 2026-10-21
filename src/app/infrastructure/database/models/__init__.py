"""ORM models.

Importing this package registers every model on `Base.metadata`, which is
required by Alembic (autogenerate) and by `create_all`.

NOTE: `scripts/generate_crud.py` appends new model imports (explicit
re-exports) to this file automatically.
"""

from app.infrastructure.database.models.task import TaskModel as TaskModel
from app.infrastructure.database.models.user import UserModel as UserModel
