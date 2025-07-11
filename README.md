# 📘 Jacinto Bemelhor Access Model Documentation

*This is the golden source for understanding, contributing to, and running the ****Jacinto Bemelhor**** access and entitlement system.*

---

## 🧭 Project Overview

Jacinto Bemelhor is a platform for sharing clinical cases and learning through quests. Access to resources is controlled through an advanced model of entitlements and invite tokens.

---

## 📦 Project Structure

### 🔙 Backend

- `models.py`: defines all database models
- `views.py`: contains all business logic and permission enforcement
- `serializers.py`: handles data representation for API endpoints
- `urls.py`: declares the routes
- `admin.py`: provides custom admin functionalities
- `api.py`: lightweight API for Person model (used in admin/test context)
- `apps.py`: registers the Django app `harena`

### 🧑‍💻 Frontend (Harena Space)

> *To be completed with screenshots once access is restored.*

- `pages/invite/quest/[token].tsx`: handles quest access token consumption
- `components/QuestEditor`: manage quests (view/edit/create)
- `components/CaseCard`: renders clinical cases
- `components/ProfileMenu`: shows user roles and logout

---

## 🛠️ Running the System

### ✅ Prerequisites

- Python 3.10+
- PostgreSQL
- Node.js + Yarn (for frontend)

### ▶️ Backend Setup

Update the `.env` secrets. 
```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
cd mundorum
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

For more information, check these four key files:
* [setup-postgresql.md](docs/setup-postgresql.md): to set the PostgreSQL DBMS for the first time;
* [setup-django.md](docs/setup-django.md): to set the Django server for the first time;
* [run.md](docs/run.md): to run the server as the setup is configured;
* [step-by-step.md](docs/step-by-step.md): to understand step-by-step how this server setup was produced.

### 💻 Frontend Setup (Harena Space)

In the harena-space folder, run the terminal 
```bash
npm run dev 
```

For mor information, check this three key files:
* [setup.md](): to set the npm environment for the first time;
* [run.md](): to run the Vite server as the setup is configured;
* [step-by-step.md]: to understand step-by-step how this server setup was produced (under construction).
---


## 🏛️ Entities and Attributes 


| Entity                   | Description                                                                             | Key Attributes                                                               |
| ------------------------ | --------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| **Institution**          | An organization (e.g., university, hospital). Holds users and quests.                   | `id`, `name`, `active`, `owner`                                              |
| **Person**               | Represents a user (student, professor, guest, owner).                                   | `user`, `google_id`, `role`, `institution`, `profile_picture`, `birth`       |
| **Quest**                | A learning group or collection of cases.                                                | `id`, `name`, `institution`, `owner`, `visible_to_institution`               |
| **Case**                 | A clinical case included in quests.                                                     | `id`, `name`, `description`, `content`, `answer`, `complexity`, `case_owner` |
**QuestCase**              | Relationship between quests and cases | `quest_id`, `case_id`
| **QuestAccessToken**     | A token used to invite users to a specific quest with predefined roles and permissions. | `token`, `quest`, `role`, `group`, `expires_at`, `max_uses`, `used_by`       |
| **ProfessorInviteToken** | A token used by institution owners to invite users to join as professors.               | `token`, `email`, `institution`, `expires_at`, `is_used`                     |
| **InstitutionDomain**    | Links email domains to institutions for automatic role assignment.                      | `name`, `institution`                                                        |



---

## 👤 User Roles

| Role          | Description                                          |
| ------------- | ---------------------------------------------------- |
| **guest**     | Temporary, limited access via invite                 |
| **student**   | Authenticated with institutional email               |
| **professor** | Authenticated with institutional email               |


⚠️ **Institution owner** and **quest owner** are not roles, but attributes within the Institution and the Quest.

---

## 👥 Group-based Access

Each quest dynamically creates three Django Groups:

- `viewers_<quest_id>` → can view cases
- `authors_<quest_id>` → can add cases
- `editors_<quest_id>` → can add, remove, reorder cases

---

## 🧩 Tokens: Authentication and Invitations

### 1. 🔐 Standard Login

- Auth via Google
- Email domain must match active institution
- Role assigned: `student`

### 2. 🎓 Professor Invite Token

- Issued by institution owner
- Limited to a specific email
- Once the token is issued, the professor get a link via email
- On usage:
  - Validates email & expiration
  - Assigns role = `professor`
  - Links to institution

### 3. 🎯 Quest Access Token

Used to invite users to participate in a specific quest.

| Field        | Description                                                  |
| ------------ | ------------------------------------------------------------ |
| `role`       | Role assigned to user (e.g. `guest`, `student`, `professor`) |
| `group`      | Group to assign (e.g. `viewer`, `author`, `editor`)          |
| `max_uses`   | Optional usage cap                                           |
| `expires_at` | Expiration datetime                                          |

✅ **Dynamic behavior**:

- If role = `guest` → account created if needed
- If role = `student/professor` → user must already belong to matching institution

Sample usage URL:

```bash
https://clienturl.com/invite/quest/<token>
```

---

## 🔐 Permissions Matrix

| Resource    | Action          | Owner | Professor | Author | Editor | Viewer | Guest |
| ----------- | --------------- | ----- | --------- | ------ | ------ | ------ | ----- |
| Institution | Manage          | ✅     | ❌         | ❌      | ❌      | ❌      | ❌     |
| Quest       | Create          | ✅     | ✅         | ❌      | ❌      | ❌      | ❌     |
| Quest       | View (Public)   | ✅     | ✅         | ✅      | ✅      | ✅      | ❌     |
| Quest       | View (Private)  | ✅     | ✅         | ✅      | ✅      | ✅      | ✅\*   |
| Quest       | Edit Metadata   | ✅     | ❌         | ❌      | ✅      | ❌      | ❌     |
| Quest       | Add/Remove Case | ✅     | ❌         | ✅      | ✅      | ❌      | ❌     |
| Case        | View            | ✅     | ✅         | ✅      | ✅      | ✅      | ✅     |
| Case        | Create/Edit     | ✅     | ✅         | ❌      | ❌      | ❌      | ❌     |

→ `*` Guest only if added via `viewer_guest` token.

---

## 🧠 Authentication Rules (Summary)

1. 🧪 **Standard**: Google login → user must match email domain of active institution
2. 🧑‍🏫 **Professor Invite Token**: email-specific, creates professor role
3. 🧩 **Quest Access Token**: allows flexible user creation/assignment for one quest only


---

## 🖼️ Diagrams

### 📊 Access Schema



### 🧬 Database Model Schema

The database schema is defined in [`models.py`](mundorum/harena/models.py). The diagram below provides a visual overview of the models and their relationships.

**Schema Diagram Path:** 

![Model Schema](mundorum/schema_clean.png)



---


## ⚙️ Backend Architecture

### Key Python Files

| File | Description |
| :--- | :--- |
| [`views.py`](mundorum/harena/views.py) | Contains the core application logic for handling API requests. This includes user authentication, creating quests, managing tokens, etc. |
| [`models.py`](mundorum/harena/models.py) | Defines the database schema, including all tables, fields, and relationships. |
| [`serializers.py`](mundorum/harena/serializers.py) | Defines how complex data types, like model instances, are converted to and from JSON for API communication. |
| [`urls.py`](mundorum/harena/urls.py) | Maps URL endpoints to their corresponding views in `views.py`. |
| [`admin.py`](mundorum/harena/admin.py) | Configures the Django admin interface for managing the application's data. |

### API Endpoints

The following are the main API endpoints exposed by the backend.

| Method | URL Pattern | View Name | Description |
| :------- | :------------------------------------------- | :--------------------------- | :------------------------------------------------------------------- |
| **POST** | `/auth/google/` | `GoogleAuthView` | Handles user login and registration using a Google ID token. Also processes `ProfessorInviteToken` and `QuestAccessToken` if provided. |
| **GET** | `/user/` | `UserView` | Retrieves the profile information for the currently authenticated user. |
| **POST** | `/api/invite/professor/` | `InviteProfessorView` | Creates and sends a new `ProfessorInviteToken` via email. |
| **POST** | `/api/quest-access-token/` | `CreateQuestAccessTokenView` | Creates a new `QuestAccessToken` to invite users to a quest. |
| **POST** | `/api/use-quest-token/` | `UseQuestAccessTokenView` | Allows a user to use a `QuestAccessToken` to gain access to a quest. |
| **GET** | `/api/quests/<uuid:quest_id>/` | `QuestDetailView` | Retrieves details for a specific quest. |
| **POST** | `/api/quests/create/` | `CreateQuestView` | Creates a new quest. |
| **GET** | `/api/quests/` | `QuestListView` | Lists all quests visible to the authenticated user. |
| **GET** | `/api/quests/<uuid:quest_id>/cases/` | `QuestCasesView` | Lists all cases associated with a specific quest. |
| **POST** | `/api/quests/<uuid:quest_id>/cases/add/` | `AddCaseToQuestView` | Adds a case to a quest. |
| **DELETE** | `/api/quests/<uuid:quest_id>/cases/<uuid:case_id>/remove/` | `RemoveCaseFromQuestView` | Removes a case from a quest. |
| **GET** | `/api/quests/editable/` | `EditableQuestListView` | Gets quests a user can edit. |
| **GET** | `/api/quests/<uuid:quest_id>/access-tokens/` | `QuestAccessTokenListView` | Lists all active invitation tokens for a specific quest. |
| **POST** | `/api/cases/create/` | `CreateCaseView` | Creates a new case. |
| **GET** | `/api/cases/mycases/` | `UserCaseListView` | Lists all cases created by the authenticated user. |
| **GET, PUT/PATCH, DELETE** | `/api/cases/<uuid:pk>/` | `CaseDetailView` | Retrieves details for a specific case. |


---

## 🖥️ Frontend Architecture

### Key React Components

| Component | Description |
| :-------------------- | :---------------------------------------------------------------------------------------------------------------------      |
| `App.jsx` | The root component that sets up the application's routing using `react-router-dom`.                                                     |
| `Login.jsx` | The main landing and login page. Handles Google authentication and token-based invites.                                               |
| `Quests.jsx` | Displays a list of all quests available to the current user.                                                                         |
| `QuestCases.jsx` | The "player" interface where users interact with the cases within a specific quest.                                              |
| `QuestEditor.jsx` | An administrative interface for quest owners/editors to manage a quest's details and its associated cases.                      |  
| `CreateQuest.jsx` | A form for professors to create new `Quests`.  
| `InviteToQuest.jsx` | A form for quest owners/editors to generate new `QuestAccessToken`s to invite others.                                         |
| `SeeInvitations.jsx` | A view for quest owners/editors to see all active invitation tokens, their usage, and expiration dates for a specific quest. |
| `QuestInviteRedirect.jsx` | A simple component that handles the redirect flow for users who click a quest invitation link, sending them to the login page. |
| `CreateCase.jsx` | A form component that allows users to create new clinical cases, including entering case details and submitting them to the backend. |
| `MyCases.jsx` | Displays a list of all clinical cases created by the current user, in a published or draft state, allowing them to view, edit, delete or manage their own cases. |
| `InviteProfessor.jsx` | Allows institution owners to generate professor invitation links and automatically send them via email. |


-----


## 🖼️ UI Walkthroughs

* **User Login and Registration Flow**
    * *Video/GIF of a new institutional user logging in for the first time. (TBD)*
    ![]()
    * *Video/GIF of a professor user using a professor invite link. (TBD)*
    ![]()
    * *Video/GIF of a guest user using a quest invite link.(TBD)*
    ![]()

* **Generating and Using Invite Links**
    * Inviting a Professor:
        ![](frontendscreenshots/inviteaprofessor.png)
    * Inviting to Quest:
        ![](frontendscreenshots/invitetoquest.png)
    * *Screenshot of the 'See All Invitations' page. (TBD)*

* **Quest Creation and Management**
    * Creating a Quest:
        ![](frontendscreenshots/createaquest.png)
    * New Quest Created:
    ![](frontendscreenshots/newquestcreated.png)
    * Editing a Quest:
        ![](frontendscreenshots/editingaquest.png)



* **Creating and Editing Cases**
    * Creating a Case:
        ![](frontendscreenshots/createacase.png)
    * My Cases:
        ![](frontendscreenshots/mycases.png)
    * Editing a Case:
        ![](frontendscreenshots/editingacase.png)
    * New Ped Case:
        ![](frontendscreenshots/newpedcase.png)
    * Publishing a Case:
        ![](frontendscreenshots/publishingacase.png)
    * Updated Cases:
        ![](frontendscreenshots/updatedcases.png)
    * Quest with New Case:
        ![](frontendscreenshots/questwithnewcase.png)


<!-- end list -->


---

## ✨ Acknowledgments

Jacinto Bemelhor is developed by the Harena Lab — Unicamp.

Maintained by: @santanche\
Access Model implemented by: @gigennari

---

## 📫 Contact

For questions or contributions, reach out via [GitHub Issues](https://github.com/harena-lab/harena-docs/issues) or email the maintainer.

---

