from pydantic import BaseModel,EmailStr
from typing import Optional,List
from datetime import datetime,date
from enum import Enum



# Schema for the request body when creating a user
class CreateUser(BaseModel):
    name: str
    email: EmailStr
    password: str
    room_number: int


# Schema for the response body when a user is created/retrieved
class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    room_number: int
    role : str
    is_mess_active: bool
    created_at: datetime

    class Config:
        from_attributes = True # Formerly orm_mode= True


#-------------------Meal Booking----------------------#
class MealBookingCreate(BaseModel):
    booking_date: date
    lunch_pick: Optional[List[str]] = None
    dinner_pick: Optional[List[str]] = None


class LunchUpdate(BaseModel):
    booking_date: date
    lunch_pick: Optional[List[str]] = None

class DinnerUpdate(BaseModel):
    booking_date: date
    dinner_pick: Optional[List[str]] = None

class MyBookingHistoryItem(BaseModel):
    booking_date: date
    lunch_pick: Optional[List[str]] = None
    dinner_pick: Optional[List[str]] = None
    created_at: datetime

# Schema for viewing an existing meal booking
class MealBookingOut(BaseModel):
    id: int
    user_id: int
    booking_date: date
    lunch_pick: Optional[List[str]] = None
    dinner_pick: Optional[List[str]] = None
    created_at: datetime

    class Config:
        from_attributes = True


#---------------------------JWT TOKEN----------------------------#
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: int | None = None



#-----------------------------MENU--------------------------------#
class DailyMenuCreate(BaseModel):
    menu_date: date
    lunch_options: List[str]
    dinner_options: List[str]


class DailyMenuOut(BaseModel):
    menu_date: date
    lunch_options: List[str]
    dinner_options: List[str]
    set_by_user_id: int

    class Config:
        from_attributes = True




#--------------------------------------Notices------------------------------------#
class NoticeCreate(BaseModel):
    title: str
    content: str


class NoticeOut(BaseModel):
    id: int
    title: str
    content: str
    name: Optional[str] = None
    posted_by_user_id: int
    created_at: datetime

    class Config:
        from_attributes = True


#------------------------------------MEAL LIST------------------------------------#
# This schema represents a single student's booking in the convenor's list.
class MealListItem(BaseModel):
    user_name: str
    room_number: int
    lunch_pick: Optional[List[str]] = None
    dinner_pick: Optional[List[str]] = None

# This is the final, complete response model for the meal list endpoints.
# It includes the detailed list of bookings and a helpful summary of item counts.
class MealListOut(BaseModel):
    booking_date: date
    total_lunch_bookings: int
    total_dinner_bookings: int
    lunch_item_counts: dict
    dinner_item_counts: dict
    bookings: List[MealListItem]

    class Config:
        from_attributes = True


#-------------------User Management Schemas (Mess Committee)----------------------#
class UserRole(str, Enum):
    student = "student"
    convenor = "convenor"
    mess_committee = "mess_committee"

class UserRoleUpdate(BaseModel):
    role: UserRole



#--------------------------------Reset Password-------------------------------#
#schema for user's initial "Forgot Password" request
class PasswordResetRequest(BaseModel):
    email: EmailStr

#schema for final reset password action
class PasswordReset(BaseModel):
    token: str
    new_password: str

    


#-----------------------------Update Mess Meal Status---------------------------#
# For the Mess Committee to update a user's status
class UserMessStatusUpdate(BaseModel):
    is_mess_active: bool




#-----------------------------Push Notification Token---------------------------#
# Schema for the mobile app to send its push token
class PushTokenUpdate(BaseModel):
    token: str


# Schema for an admin to send a notification (for the manual send endpoint)
class NotificationCreate(BaseModel):
    title: str
    message: str

#---------------------------Update User Info----------------------------#
class UpdatedUserIn(BaseModel):
    name: str
    room_number: int

class UpdatedUserOut(BaseModel):
    id: int
    name: str
    room_number: int
