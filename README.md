# MessBook

This repository contains the complete description for **MessBook**, a backend of hostel mess management application.

## About MessBook

MessBook is a comprehensive application built to digitize and streamline hostel mess operations. It provides a simple interface for students to manage their meals and a powerful dashboard for administrators to manage the mess.

## Tech Stack

This project leverages a modern, robust tech stack:

* **Backend:** `FastAPI` (Python)
* **Database:** `PostgreSQL`
* **Frontend:** `Flutter` (Dart) which is developed by my collaborator of the project

## Core API Features

The backend API is designed around REST principles and includes the following features:

* **User Authentication:** Secure token-based (OAuth2) authentication for students and administrators.
* **Meal Booking:** Endpoints for students to book or cancel their meals for specific dates or time slots.
* **Menu Management:** Admin-only routes to create, update, and publish the weekly/daily mess menu.
* **Notice Board:** Admin routes to post announcements; student routes to fetch all active notices.
* **User Management:** Admin controls to manage student accounts, including the ability to enable or disable mess access for individuals.
* **Profile Management:** Endpoints for users to view their account info and change their password.
