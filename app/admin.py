"""
SQLAdmin configuration for the Demo SIS.
Provides a web UI at /admin/ for managing all SS12000 entities.
"""
from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

from .config import get_settings
from .models.organisation import Organisation
from .models.person import Person, Enrolment
from .models.group import Group, GroupMembership
from .models.duty import Duty, DutyAssignment
from .models.activity import Activity, ActivityTeacher, ActivityGroup


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = form.get("username")
        password = form.get("password")
        settings = get_settings()
        if username == settings.admin_username and password == settings.admin_password:
            request.session.update({"authenticated": True})
            return True
        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return request.session.get("authenticated", False)


class OrganisationAdmin(ModelView, model=Organisation):
    column_list = [
        Organisation.display_name,
        Organisation.organisation_type,
        Organisation.school_unit_code,
        Organisation.parent_id,
    ]
    column_searchable_list = [Organisation.display_name]
    column_sortable_list = [Organisation.display_name, Organisation.organisation_type]
    name = "Organisation"
    name_plural = "Organisations"
    icon = "fa-solid fa-building"


class PersonAdmin(ModelView, model=Person):
    column_list = [
        Person.given_name,
        Person.family_name,
        Person.email,
        Person.person_status,
        Person.external_id,
    ]
    column_searchable_list = [Person.given_name, Person.family_name, Person.email, Person.external_id]
    column_sortable_list = [Person.given_name, Person.family_name, Person.email]
    column_default_sort = "family_name"
    name = "Person"
    name_plural = "Persons"
    icon = "fa-solid fa-user"


class EnrolmentAdmin(ModelView, model=Enrolment):
    column_list = [
        Enrolment.person_id,
        Enrolment.organisation_id,
        Enrolment.school_type,
        Enrolment.school_year,
    ]
    name = "Enrolment"
    name_plural = "Enrolments"
    icon = "fa-solid fa-graduation-cap"


class GroupAdmin(ModelView, model=Group):
    column_list = [
        Group.display_name,
        Group.group_type,
        Group.school_type,
        Group.organisation_id,
    ]
    column_searchable_list = [Group.display_name, Group.group_code]
    column_sortable_list = [Group.display_name, Group.group_type]
    column_default_sort = "display_name"
    name = "Group"
    name_plural = "Groups"
    icon = "fa-solid fa-users"


class GroupMembershipAdmin(ModelView, model=GroupMembership):
    column_list = [
        GroupMembership.group_id,
        GroupMembership.person_id,
        GroupMembership.start_date,
    ]
    name = "Group Membership"
    name_plural = "Group Memberships"
    icon = "fa-solid fa-user-plus"


class DutyAdmin(ModelView, model=Duty):
    column_list = [
        Duty.person_id,
        Duty.organisation_id,
        Duty.duty_role,
        Duty.signature,
        Duty.start_date,
    ]
    column_searchable_list = [Duty.duty_role, Duty.signature]
    column_sortable_list = [Duty.duty_role]
    name = "Duty"
    name_plural = "Duties"
    icon = "fa-solid fa-briefcase"


class DutyAssignmentAdmin(ModelView, model=DutyAssignment):
    column_list = [
        DutyAssignment.duty_id,
        DutyAssignment.group_id,
        DutyAssignment.assignment_role_type,
    ]
    name = "Duty Assignment"
    name_plural = "Duty Assignments"
    icon = "fa-solid fa-link"


class ActivityAdmin(ModelView, model=Activity):
    column_list = [
        Activity.display_name,
        Activity.activity_type,
        Activity.subject_code,
        Activity.subject_name,
        Activity.organisation_id,
    ]
    column_searchable_list = [Activity.display_name, Activity.subject_code]
    column_sortable_list = [Activity.display_name, Activity.subject_code]
    name = "Activity"
    name_plural = "Activities"
    icon = "fa-solid fa-book"


class ActivityTeacherAdmin(ModelView, model=ActivityTeacher):
    column_list = [
        ActivityTeacher.activity_id,
        ActivityTeacher.person_id,
        ActivityTeacher.allocation_percent,
    ]
    name = "Activity Teacher"
    name_plural = "Activity Teachers"
    icon = "fa-solid fa-chalkboard-teacher"


class ActivityGroupAdmin(ModelView, model=ActivityGroup):
    column_list = [
        ActivityGroup.activity_id,
        ActivityGroup.group_id,
    ]
    name = "Activity Group"
    name_plural = "Activity Groups"
    icon = "fa-solid fa-layer-group"


def setup_admin(app, engine):
    """Register SQLAdmin with the FastAPI app."""
    settings = get_settings()
    auth_backend = AdminAuth(secret_key=settings.admin_secret)
    admin = Admin(app, engine, title="Demo SIS Admin", authentication_backend=auth_backend)
    admin.add_view(OrganisationAdmin)
    admin.add_view(PersonAdmin)
    admin.add_view(EnrolmentAdmin)
    admin.add_view(GroupAdmin)
    admin.add_view(GroupMembershipAdmin)
    admin.add_view(DutyAdmin)
    admin.add_view(DutyAssignmentAdmin)
    admin.add_view(ActivityAdmin)
    admin.add_view(ActivityTeacherAdmin)
    admin.add_view(ActivityGroupAdmin)
