from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.views.decorators.http import require_POST

from yaksh.models import Course, Quiz, Lesson

from .models import Permission, Role, Team
from .utils import format_perm


# Create your views here.


@login_required
def home(request):
    user = request.user
    # Get users
    users = User.objects.all().exclude(username=user.username)
    teams = user.team_members.all()
    courses = Course.objects.filter(creator=user)

    context = {
        "users": users,
        "teams": teams,
        "courses": courses
    }

    return render(request, "home.html", context)


@require_POST
@login_required
def create_team(request):
    user = request.user
    team_name = request.POST.get("team_name")
    members_list = request.POST.getlist("members")
    courses_list = request.POST.getlist("courses")

    if len(team_name) > 0:
        team = Team.objects.create(
            name=team_name,
            created_by=user
        )

        members = User.objects.filter(username__in=members_list)
        team.members.add(*members)
        team.members.add(user)

        courses = Course.objects.filter(id__in=courses_list)
        team.courses.add(*courses)

        team.save()

    return redirect("permissions:home")


@login_required()
def team_detail(request, team_id):
    users = User.objects.all()

    context = {
        "users": users
    }

    try:
        team = Team.objects.get(id=team_id)
        roles = Role.objects.filter(team=team)
        permissions = Permission.objects.filter(team=team)
        context["team"] = team
        context["roles"] = roles
        context["permissions"] = format_perm(permissions)
        context["courses"] = team.courses.all()

        role_map = {}

        for member in team.members.all():
            member_roles = list(
                map(lambda x: x.name, member.role_set.filter(team=team)))
            role_map[member.username] = ",".join(member_roles)

        context["role_map"] = role_map

    except Team.DoesNotExist:
        return redirect("permissions:home")

    return render(request, "team_page.html", context)


@require_POST
@login_required
def create_role(request):
    team_id = request.POST.get("team_id")
    role_name = request.POST.get("role_name")
    members_list = request.POST.getlist("members")

    try:
        team = Team.objects.get(id=team_id)
        role = Role(
            name=role_name,
            created_by=request.user,
            team=team
        )

        role.save()

        members = User.objects.filter(username__in=members_list)
        role.members.add(*members)

        role.save()
    except Team.DoesNotExist:
        return redirect('permissions:home')

    return redirect('permissions:team_detail', team_id)


@require_POST
@login_required
def add_permission(request):
    team_id = request.POST.get("team_id")
    course_id = request.POST.get("courses")
    role_id = request.POST.get("role")
    perm_type = request.POST.get("perm_type")
    units = request.POST.getlist("units")

    team = Team.objects.get(id=team_id)
    course = Course.objects.get(id=course_id)
    role = Role.objects.get(id=role_id)

    # Create permission obj for each unit
    for unit in units:
        type, id = unit.split("_")

        if type == "quiz":
            content_object = Quiz.objects.get(pk=id)
        else:
            content_object = Lesson.objects.get(pk=id)

        permission = Permission(
            team=team,
            course=course,
            perm_type=perm_type,
            content_object=content_object
        )

        permission.save()

        permission.role.add(role)

        permission.save()

    return redirect('permissions:team_detail', team_id)


@login_required
def delete_permission(request, permission_id, team_id):
    '''
    Delete permission.
    Only team creator can delete
    '''

    try:
        team = Team.objects.get(pk=team_id)

        if team.created_by == request.user:
            Permission.objects.get(pk=permission_id).delete()

            return redirect('permissions:team_detail', team_id)
    except Team.DoesNotExist:
        return redirect('permissions:home')


@login_required
def get_modules(request):
    ''' Get modules belonging to a course '''

    course_id = request.GET.get("course_id")
    course = get_object_or_404(Course, pk=course_id)
    modules = course.learning_module.all()

    units = []

    for module in modules:
        quiz_units = module.get_quiz_units()
        lesson_units = module.get_lesson_units()

        quiz_units_data = [
            {"key": "quiz_{}".format(quiz_unit.id),
             "name": quiz_unit.description} for quiz_unit in quiz_units
        ]

        lesson_units_data = [
            {"key": "lesson_{}".format(lesson_unit.id),
             "name": lesson_unit.name} for lesson_unit in lesson_units
        ]

        units = quiz_units_data + lesson_units_data

    data = {
        "units": units
    }

    return JsonResponse(data)