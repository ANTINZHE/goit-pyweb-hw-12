from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, extract
from typing import List, Optional
from datetime import date, timedelta

import models, schemas
from database import engine, get_db

# Створення таблиць в БД
models.Base.metadata.create_all(bind=engine)

app = FastAPI()


# 1. Створити новий контакт
@app.post("/contacts/", response_model=schemas.ContactResponse)
def create_contact(contact: schemas.ContactCreate, db: Session = Depends(get_db)):
    # Перевірка на існування email
    db_contact = db.query(models.Contact).filter(models.Contact.email == contact.email).first()
    if db_contact:
        raise HTTPException(status_code=400, detail="Email already registered")

    new_contact = models.Contact(**contact.dict())
    db.add(new_contact)
    db.commit()
    db.refresh(new_contact)
    return new_contact


# 2. Отримати список контактів (з пошуком)
@app.get("/contacts/", response_model=List[schemas.ContactResponse])
def read_contacts(
        skip: int = 0,
        limit: int = 100,
        q: Optional[str] = Query(None, description="Пошук за ім'ям, прізвищем або email"),
        db: Session = Depends(get_db)
):
    query = db.query(models.Contact)

    if q:
        # Логіка пошуку: шукаємо збіг у будь-якому з 3 полів
        query = query.filter(
            or_(
                models.Contact.first_name.ilike(f"%{q}%"),
                models.Contact.last_name.ilike(f"%{q}%"),
                models.Contact.email.ilike(f"%{q}%")
            )
        )

    contacts = query.offset(skip).limit(limit).all()
    return contacts


# 3. Отримати найближчі дні народження (7 днів)
@app.get("/contacts/birthdays", response_model=List[schemas.ContactResponse])
def upcoming_birthdays(db: Session = Depends(get_db)):
    today = date.today()
    end_date = today + timedelta(days=7)

    contacts = []
    all_contacts = db.query(models.Contact).all()

    # Логіка перевірки дати (ігноруючи рік народження)
    for contact in all_contacts:
        if contact.birthday:
            # Замінюємо рік народження на поточний рік для перевірки
            bday_this_year = contact.birthday.replace(year=today.year)

            if today <= bday_this_year <= end_date:
                contacts.append(contact)

            # Обробка випадку кінця року (якщо сьогодні 30 грудня, а ДН 2 січня)
            # Перевіряємо наступний рік
            bday_next_year = contact.birthday.replace(year=today.year + 1)
            if today <= bday_next_year <= end_date:
                contacts.append(contact)

    return contacts


# 4. Отримати один контакт
@app.get("/contacts/{contact_id}", response_model=schemas.ContactResponse)
def read_contact(contact_id: int, db: Session = Depends(get_db)):
    contact = db.query(models.Contact).filter(models.Contact.id == contact_id).first()
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


# 5. Оновити контакт
@app.put("/contacts/{contact_id}", response_model=schemas.ContactResponse)
def update_contact(contact_id: int, contact_update: schemas.ContactUpdate, db: Session = Depends(get_db)):
    contact = db.query(models.Contact).filter(models.Contact.id == contact_id).first()
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")

    # Оновлюємо тільки ті поля, що були передані
    for key, value in contact_update.dict(exclude_unset=True).items():
        setattr(contact, key, value)

    db.commit()
    db.refresh(contact)
    return contact


# 6. Видалити контакт
@app.delete("/contacts/{contact_id}")
def delete_contact(contact_id: int, db: Session = Depends(get_db)):
    contact = db.query(models.Contact).filter(models.Contact.id == contact_id).first()
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")

    db.delete(contact)
    db.commit()
    return {"detail": "Contact deleted"}