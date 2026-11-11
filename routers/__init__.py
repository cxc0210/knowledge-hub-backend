from routers.auth import router as auth_router
from routers.document import router as document_router
from routers.document_content import router as document_content_router
from routers.user import router as user_router

__all__ = ["auth_router", "document_content_router", "document_router", "user_router"]
