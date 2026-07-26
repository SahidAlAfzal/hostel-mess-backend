from sqlalchemy import Column, Boolean, ForeignKey, String, Integer, text, Text, Date, UniqueConstraint
from sqlalchemy.orm import declarative_base
from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import ARRAY, TIMESTAMP


Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    hashed_password = Column(Text, nullable=False)
    room_number = Column(Integer)
    # Use server_default to tell Alembic the database handles the default
    role = Column(String(50), nullable=False, server_default='student')
    is_active = Column(Boolean, nullable=False, server_default=text("false"))
    is_mess_active = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    push_token = Column(Text)
    

class Notice(Base):
    __tablename__ = "notices"
    
    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    posted_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    name = Column(String(255))

    
class Menu(Base):
    __tablename__ = "daily_menus"
    
    id = Column(Integer, primary_key=True)
    menu_date = Column(Date, unique=True, nullable=False, index=True)
    lunch_options = Column(ARRAY(Text), nullable=False)
    dinner_options = Column(ARRAY(Text), nullable=False)
    set_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    
    
class Booking(Base):
    __tablename__ = "meal_bookings"
    
    # __table_args__ to map the composite unique constraint
    __table_args__ = (
        UniqueConstraint('user_id', 'booking_date', name='meal_bookings_user_id_booking_date_key'),
    )
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Removed unique=True from here
    booking_date = Column(Date, nullable=False) 
    
    lunch_pick = Column(ARRAY(Text))
    dinner_pick = Column(ARRAY(Text))
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    
    
    
class Cooldown(Base):
    __tablename__ = "system_cooldowns"
    
    task_name = Column(Text, primary_key=True)
    last_triggered_at = Column(TIMESTAMP(timezone=True))
    
    
class IssueTicket(Base):
    __tablename__ = "issue_tickets"
    
    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    description = Column(String(255), nullable=False)
    image_url = Column(Text, nullable=False)
    
    
    # Tracking the reporter
    posted_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    
    
    # Tracking the resolution
    is_resolved = Column(Boolean, nullable=False, server_default=text("false"))
    resolved_at = Column(TIMESTAMP(timezone=True), nullable=True)
    resolved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    