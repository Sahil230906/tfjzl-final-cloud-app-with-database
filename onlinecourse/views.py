
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.views import generic
from django.views.decorators.http import require_POST
import logging

from .models import Course, Enrollment, Submission, Question, Choice

logger = logging.getLogger(__name__)


# User Registration
def registration_request(request):
    context = {}

    if request.method == 'GET':
        return render(
            request,
            'onlinecourse/user_registration_bootstrap.html',
            context
        )

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('psw')
        first_name = request.POST.get('firstname', '')
        last_name = request.POST.get('lastname', '')

        if User.objects.filter(username=username).exists():
            context['message'] = 'User already exists.'
            return render(
                request,
                'onlinecourse/user_registration_bootstrap.html',
                context
            )

        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=first_name,
            last_name=last_name
        )

        login(request, user)
        return redirect('onlinecourse:index')


# User Login
def login_request(request):
    context = {}

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('psw')

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:
            login(request, user)
            return redirect('onlinecourse:index')

        context['message'] = 'Invalid username or password.'

    return render(
        request,
        'onlinecourse/user_login_bootstrap.html',
        context
    )


# User Logout
def logout_request(request):
    logout(request)
    return redirect('onlinecourse:index')


# Check Whether User Is Enrolled
def check_if_enrolled(user, course):
    if not user.is_authenticated:
        return False

    return Enrollment.objects.filter(
        user=user,
        course=course
    ).exists()


# Course List
class CourseListView(generic.ListView):
    template_name = 'onlinecourse/course_list_bootstrap.html'
    context_object_name = 'course_list'

    def get_queryset(self):
        user = self.request.user
        courses = Course.objects.order_by('-total_enrollment')[:10]

        for course in courses:
            if user.is_authenticated:
                course.is_enrolled = check_if_enrolled(user, course)
            else:
                course.is_enrolled = False

        return courses


# Course Details
class CourseDetailView(generic.DetailView):
    model = Course
    template_name = 'onlinecourse/course_details_bootstrap.html'


# Enroll in a Course
@login_required
def enroll(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    user = request.user

    if not check_if_enrolled(user, course):
        Enrollment.objects.create(
            user=user,
            course=course,
            mode='honor'
        )

        course.total_enrollment += 1
        course.save()

    return redirect(
        'onlinecourse:course_details',
        pk=course.id
    )


# Extract Selected Answers from Exam Form
def extract_answers(request):
    submitted_answers = []

    for key, value in request.POST.items():
        if key.startswith('choice_') or key.startswith('question_'):
            try:
                submitted_answers.append(int(value))
            except (ValueError, TypeError):
                continue

    return submitted_answers


# Submit Exam
@login_required
@require_POST
def submit(request, course_id):
    course = get_object_or_404(Course, pk=course_id)

    enrollment = get_object_or_404(
        Enrollment,
        user=request.user,
        course=course
    )

    submission = Submission.objects.create(
        enrollment=enrollment
    )

    answer_ids = set(extract_answers(request))

    valid_choices = Choice.objects.filter(
        id__in=answer_ids,
        question__course=course
    )

    submission.choices.set(valid_choices)

    return redirect(
        'onlinecourse:show_exam_result',
        course_id=course.id,
        submission_id=submission.id
    )


# Display Exam Results
@login_required
def show_exam_result(request, course_id, submission_id):
    course = get_object_or_404(Course, pk=course_id)

    submission = get_object_or_404(
        Submission,
        pk=submission_id,
        enrollment__user=request.user,
        enrollment__course=course
    )

    selected_ids = set(
        submission.choices.values_list('id', flat=True)
    )

    questions = Question.objects.filter(course=course)

    question_results = []
    total_score = 0
    possible_score = 0

    for question in questions:
        choices = Choice.objects.filter(question=question)
        correct_choices = choices.filter(is_correct=True)
        selected_choices = choices.filter(id__in=selected_ids)

        is_correct = question.is_get_score(selected_ids)

        possible_score += question.grade

        if is_correct:
            total_score += question.grade

        question_results.append({
            'question': question,
            'choices': choices,
            'correct_choices': correct_choices,
            'selected_choices': selected_choices,
            'is_correct': is_correct,
        })

    score = (
        round((total_score / possible_score) * 100, 2)
        if possible_score > 0
        else 0
    )

    context = {
        'course': course,
        'submission': submission,
        'question_results': question_results,
        'total_score': total_score,
        'possible_score': possible_score,
        'score': score,
        'passed': score >= 50,
    }

    return render(
        request,
        'onlinecourse/exam_result_bootstrap.html',
        context
    )
