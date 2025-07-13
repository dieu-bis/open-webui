from pydantic import BaseModel
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, func
from typing import Optional
from datetime import datetime

from open_webui.internal.db import Base, get_db


####################
# Atlassian Connection DB Schema
####################


class AtlassianConnection(Base):
    __tablename__ = "atlassian_connections"

    id = Column(Integer, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    atlassian_account_id = Column(String, nullable=False)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=False)
    token_expires_at = Column(DateTime, nullable=False)
    scopes = Column(Text, nullable=False)  # Space-separated scopes
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    def __repr__(self):
        return f"<AtlassianConnection(id={self.id}, user_id={self.user_id}, account_id={self.atlassian_account_id})>"


####################
# Forms
####################


class AtlassianConnectionForm(BaseModel):
    user_id: str
    atlassian_account_id: str
    access_token: str
    refresh_token: str
    token_expires_at: datetime
    scopes: str
    is_active: bool = True


class AtlassianConnectionResponse(BaseModel):
    id: int
    user_id: str
    atlassian_account_id: str
    scopes: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AtlassianSiteInfo(BaseModel):
    id: str  # cloudid
    name: str
    url: str
    scopes: list[str]
    avatar_url: Optional[str] = None


####################
# AtlassianConnections
####################


class AtlassianConnections:
    def get_connection_by_user_id(self, user_id: str) -> Optional[AtlassianConnection]:
        """Get active Atlassian connection for a user"""
        with get_db() as db:
            return (
                db.query(AtlassianConnection)
                .filter(
                    AtlassianConnection.user_id == user_id,
                    AtlassianConnection.is_active == True
                )
                .first()
            )

    def create_connection(self, form_data: AtlassianConnectionForm) -> AtlassianConnection:
        """Create a new Atlassian connection"""
        with get_db() as db:
            # Deactivate any existing connections for this user
            db.query(AtlassianConnection).filter(
                AtlassianConnection.user_id == form_data.user_id
            ).update({"is_active": False})

            connection = AtlassianConnection(
                user_id=form_data.user_id,
                atlassian_account_id=form_data.atlassian_account_id,
                access_token=form_data.access_token,
                refresh_token=form_data.refresh_token,
                token_expires_at=form_data.token_expires_at,
                scopes=form_data.scopes,
                is_active=form_data.is_active,
            )
            db.add(connection)
            db.commit()
            db.refresh(connection)
            return connection

    def update_tokens(
        self, 
        user_id: str, 
        access_token: str, 
        refresh_token: str, 
        token_expires_at: datetime
    ) -> Optional[AtlassianConnection]:
        """Update tokens for an existing connection"""
        with get_db() as db:
            connection = (
                db.query(AtlassianConnection)
                .filter(
                    AtlassianConnection.user_id == user_id,
                    AtlassianConnection.is_active == True
                )
                .first()
            )
            
            if connection:
                connection.access_token = access_token
                connection.refresh_token = refresh_token
                connection.token_expires_at = token_expires_at
                connection.updated_at = datetime.now()
                db.commit()
                db.refresh(connection)
                return connection
            return None

    def deactivate_connection(self, user_id: str) -> bool:
        """Deactivate Atlassian connection for a user"""
        with get_db() as db:
            result = (
                db.query(AtlassianConnection)
                .filter(
                    AtlassianConnection.user_id == user_id,
                    AtlassianConnection.is_active == True
                )
                .update({"is_active": False})
            )
            db.commit()
            return result > 0

    def get_all_connections(self) -> list[AtlassianConnection]:
        """Get all active Atlassian connections"""
        with get_db() as db:
            return (
                db.query(AtlassianConnection)
                .filter(AtlassianConnection.is_active == True)
                .all()
            )

    def delete_connection(self, user_id: str) -> bool:
        """Permanently delete Atlassian connection for a user"""
        with get_db() as db:
            result = (
                db.query(AtlassianConnection)
                .filter(AtlassianConnection.user_id == user_id)
                .delete()
            )
            db.commit()
            return result > 0


AtlassianConnections = AtlassianConnections()