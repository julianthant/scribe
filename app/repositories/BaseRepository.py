"""
BaseRepository.py - Base Repository Pattern Implementation

Provides base repository class following domain-driven design principles.
This module implements:
- Generic CRUD operations for all domain entities
- Type-safe repository pattern with generics
- Async database session management
- Common query patterns and filters

All domain repositories should inherit from BaseRepository to ensure
consistent data access patterns across the application.
"""

import logging
from abc import ABC
from typing import Any, Dict, Generic, List, Optional, TypeVar, Union

from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.core.Exceptions import DatabaseError
from app.models.DatabaseModel import Base

logger = logging.getLogger(__name__)

# Type variables for generic repository
ModelType = TypeVar('ModelType', bound=Base)
CreateSchemaType = TypeVar('CreateSchemaType')
UpdateSchemaType = TypeVar('UpdateSchemaType')


class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType], ABC):
    """
    Base repository class for all domain repositories.
    
    Provides common CRUD operations and query patterns using SQLAlchemy async sessions.
    All domain repositories should inherit from this class to ensure consistency.
    
    Type Parameters:
        ModelType: SQLAlchemy model class
        CreateSchemaType: Schema for creating new entities
        UpdateSchemaType: Schema for updating existing entities
    """
    
    def __init__(self, model: type[ModelType], db_session: AsyncSession):
        """
        Initialize repository with model class and database session.
        
        Args:
            model: SQLAlchemy model class
            db_session: Async database session
        """
        self.model = model
        self.db_session = db_session
    
    async def create(self, obj_data: Union[CreateSchemaType, Dict[str, Any]]) -> ModelType:
        """
        Create a new entity.
        
        Args:
            obj_data: Data for creating the entity (schema or dict)
            
        Returns:
            Created entity instance
            
        Raises:
            DatabaseError: If creation fails
        """
        try:
            # Convert schema to dict if needed
            if hasattr(obj_data, 'model_dump'):
                data_dict = obj_data.model_dump()
            elif hasattr(obj_data, 'dict'):
                data_dict = obj_data.dict()
            else:
                data_dict = obj_data
            
            # Create entity instance
            db_obj = self.model(**data_dict)
            
            # Add to session and commit
            self.db_session.add(db_obj)
            await self.db_session.commit()
            await self.db_session.refresh(db_obj)
            
            logger.debug(f"Created {self.model.__name__} with ID: {getattr(db_obj, 'id', 'N/A')}")
            return db_obj
            
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Failed to create {self.model.__name__}: {str(e)}", exc_info=True)
            raise DatabaseError(
                f"Failed to create {self.model.__name__}",
                error_code="REPOSITORY_CREATE_FAILED",
                details={"model": self.model.__name__, "error": str(e)}
            )
    
    async def get_by_id(self, id: Any) -> Optional[ModelType]:
        """
        Get entity by ID.
        
        Args:
            id: Entity ID
            
        Returns:
            Entity instance or None if not found
        """
        try:
            result = await self.db_session.execute(
                select(self.model).where(getattr(self.model, 'id') == id)
            )
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Failed to get {self.model.__name__} by ID {id}: {str(e)}")
            return None
    
    async def get_all(
        self, 
        limit: Optional[int] = None, 
        offset: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[ModelType]:
        """
        Get all entities with optional pagination and filtering.
        
        Args:
            limit: Maximum number of entities to return
            offset: Number of entities to skip
            filters: Optional filters to apply
            
        Returns:
            List of entity instances
        """
        try:
            query = select(self.model)
            
            # Apply filters
            if filters:
                conditions = []
                for key, value in filters.items():
                    if hasattr(self.model, key):
                        conditions.append(getattr(self.model, key) == value)
                if conditions:
                    query = query.where(and_(*conditions))
            
            # Apply pagination
            if offset:
                query = query.offset(offset)
            if limit:
                query = query.limit(limit)
            
            result = await self.db_session.execute(query)
            return list(result.scalars().all())
            
        except Exception as e:
            logger.error(f"Failed to get all {self.model.__name__}: {str(e)}")
            return []
    
    async def update(
        self, 
        id_or_entity: Any, 
        obj_data: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> Optional[ModelType]:
        """
        Update an entity by ID or entity object.
        
        Args:
            id_or_entity: Entity ID or entity object
            obj_data: Update data (schema or dict)
            
        Returns:
            Updated entity instance or None if not found
            
        Raises:
            DatabaseError: If update fails
        """
        try:
            # Extract ID from entity object if passed
            if hasattr(id_or_entity, 'id'):
                entity_id = id_or_entity.id
            else:
                entity_id = id_or_entity
            
            # Convert schema to dict if needed
            if hasattr(obj_data, 'model_dump'):
                data_dict = obj_data.model_dump(exclude_unset=True)
            elif hasattr(obj_data, 'dict'):
                data_dict = obj_data.dict(exclude_unset=True)
            else:
                data_dict = obj_data
            
            # Perform update
            result = await self.db_session.execute(
                update(self.model)
                .where(getattr(self.model, 'id') == entity_id)
                .values(**data_dict)
                .returning(self.model)
            )
            
            updated_obj = result.scalar_one_or_none()
            if updated_obj:
                await self.db_session.commit()
                await self.db_session.refresh(updated_obj)
                logger.debug(f"Updated {self.model.__name__} with ID: {entity_id}")
                return updated_obj
            else:
                await self.db_session.rollback()
                return None
                
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Failed to update {self.model.__name__} {entity_id}: {str(e)}", exc_info=True)
            raise DatabaseError(
                f"Failed to update {self.model.__name__}",
                error_code="REPOSITORY_UPDATE_FAILED",
                details={"model": self.model.__name__, "id": entity_id, "error": str(e)}
            )
    
    async def delete(self, id: Any) -> bool:
        """
        Delete an entity by ID.
        
        Args:
            id: Entity ID
            
        Returns:
            True if entity was deleted, False if not found
            
        Raises:
            DatabaseError: If deletion fails
        """
        try:
            result = await self.db_session.execute(
                delete(self.model).where(getattr(self.model, 'id') == id)
            )
            
            if result.rowcount > 0:
                await self.db_session.commit()
                logger.debug(f"Deleted {self.model.__name__} with ID: {id}")
                return True
            else:
                return False
                
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Failed to delete {self.model.__name__} {id}: {str(e)}", exc_info=True)
            raise DatabaseError(
                f"Failed to delete {self.model.__name__}",
                error_code="REPOSITORY_DELETE_FAILED", 
                details={"model": self.model.__name__, "id": id, "error": str(e)}
            )
    
    async def exists(self, id: Any) -> bool:
        """
        Check if entity exists by ID.
        
        Args:
            id: Entity ID
            
        Returns:
            True if entity exists, False otherwise
        """
        try:
            result = await self.db_session.execute(
                select(getattr(self.model, 'id')).where(getattr(self.model, 'id') == id)
            )
            return result.scalar_one_or_none() is not None
            
        except Exception as e:
            logger.error(f"Failed to check if {self.model.__name__} {id} exists: {str(e)}")
            return False
    
    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Count entities with optional filters.
        
        Args:
            filters: Optional filters to apply
            
        Returns:
            Number of matching entities
        """
        try:
            query = select(self.model)
            
            if filters:
                conditions = []
                for key, value in filters.items():
                    if hasattr(self.model, key):
                        conditions.append(getattr(self.model, key) == value)
                if conditions:
                    query = query.where(and_(*conditions))
            
            result = await self.db_session.execute(query)
            entities = result.scalars().all()
            return len(entities)
            
        except Exception as e:
            logger.error(f"Failed to count {self.model.__name__}: {str(e)}")
            return 0
    
    async def find_by(self, **kwargs) -> List[ModelType]:
        """
        Find entities by arbitrary field values.
        
        Args:
            **kwargs: Field names and values to filter by
            
        Returns:
            List of matching entities
        """
        try:
            query = select(self.model)
            conditions = []
            
            for key, value in kwargs.items():
                if hasattr(self.model, key):
                    conditions.append(getattr(self.model, key) == value)
            
            if conditions:
                query = query.where(and_(*conditions))
            
            result = await self.db_session.execute(query)
            return list(result.scalars().all())
            
        except Exception as e:
            logger.error(f"Failed to find {self.model.__name__} by {kwargs}: {str(e)}")
            return []
    
    async def find_one_by(self, **kwargs) -> Optional[ModelType]:
        """
        Find single entity by arbitrary field values.
        
        Args:
            **kwargs: Field names and values to filter by
            
        Returns:
            First matching entity or None
        """
        entities = await self.find_by(**kwargs)
        return entities[0] if entities else None