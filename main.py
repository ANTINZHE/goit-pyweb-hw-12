from fastapi import FastAPI, Depends, HTTPException, Query, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from datetime import date, timedelta
from jose import JWTError, jwt

import models, schemas, auth
from database import engine, get_db

# Створюємо таблиці
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# --- НАЛАШТУВАННЯ БЕЗПЕКИ ---
security = HTTPBearer()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security),
                           db: Session = Depends(get_db)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        email = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


# --- МАРШРУТИ АУТЕНТИФІКАЦІЇ ---

@app.post("/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    hashed_password = auth.get_password_hash(user.password)
    new_user = models.User(email=user.email, password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@app.post("/login", response_model=schemas.TokenModel)
def login(user_data: schemas.LoginModel, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == user_data.email).first()
    if not user or not auth.verify_password(user_data.password, user.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access_token = auth.create_access_token(data={"sub": user.email})
    refresh_token = auth.create_refresh_token(data={"sub": user.email})

    user.refresh_token = refresh_token
    db.commit()

    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}


# --- ЗАХИЩЕНІ МАРШРУТИ ДЛЯ КОНТАКТІВ ---

# 1. Створити контакт
@app.post("/contacts/", response_model=schemas.ContactResponse, status_code=status.HTTP_201_CREATED)
def create_contact(
        contact: schemas.ContactCreate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user)
):
    new_contact = models.Contact(**contact.dict(), user_id=current_user.id)
    db.add(new_contact)
    db.commit()
    db.refresh(new_contact)
    return new_contact


# 2. Отримати всі контакти поточного користувача
@app.get("/contacts/", response_model=List[schemas.ContactResponse])
def read_contacts(
        skip: int = 0,
        limit: int = 100,
        q: Optional[str] = Query(None, description="Пошук за ім'ям, прізвищем або email"),
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user)
):
    # Починаємо запит, фільтруючи одразу по власнику
    query = db.query(models.Contact).filter(models.Contact.user_id == current_user.id)

    if q:
        query = query.filter(
            or_(
                models.Contact.first_name.ilike(f"%{q}%"),
                models.Contact.last_name.ilike(f"%{q}%"),
                models.Contact.email.ilike(f"%{q}%")
            )
        )

    return query.offset(skip).limit(limit).all()


# 3. Отримати дні народження контактів поточного користувача
@app.get("/contacts/birthdays", response_model=List[schemas.ContactResponse])
def upcoming_birthdays(
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user)
):
    today = date.today()
    end_date = today + timedelta(days=7)

    contacts = []
    # Беремо контакти тільки цього юзера
    user_contacts = db.query(models.Contact).filter(models.Contact.user_id == current_user.id).all()

    for contact in user_contacts:
        if contact.birthday:
            bday_this_year = contact.birthday.replace(year=today.year)
            if today <= bday_this_year <= end_date:
                contacts.append(contact)

            bday_next_year = contact.birthday.replace(year=today.year + 1)
            if today <= bday_next_year <= end_date:
                contacts.append(contact)

    return contacts


# 4. Отримати один конкретний контакт
@app.get("/contacts/{contact_id}", response_model=schemas.ContactResponse)
def read_contact(
        contact_id: int,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user)
):
    contact = db.query(models.Contact).filter(models.Contact.id == contact_id,
                                              models.Contact.user_id == current_user.id).first()
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


# 5. Оновити контакт
@app.put("/contacts/{contact_id}", response_model=schemas.ContactResponse)
def update_contact(
        contact_id: int,
        contact_update: schemas.ContactUpdate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user)
):
    contact = db.query(models.Contact).filter(models.Contact.id == contact_id,
                                              models.Contact.user_id == current_user.id).first()
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")

    for key, value in contact_update.dict(exclude_unset=True).items():
        setattr(contact, key, value)

    db.commit()
    db.refresh(contact)
    return contact


# 6. Видалити контакт
@app.delete("/contacts/{contact_id}")
def delete_contact(
        contact_id: int,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user)
):
    contact = db.query(models.Contact).filter(models.Contact.id == contact_id,
                                              models.Contact.user_id == current_user.id).first()
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")

    db.delete(contact)
    db.commit()
    return {"detail": "Contact deleted"}