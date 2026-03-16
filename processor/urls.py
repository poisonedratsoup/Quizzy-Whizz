from django.urls import path
from . import views

urlpatterns = [
    path("get_metadata/", views.get_metadata, name="get_metadata"),
    path("upload_content/", views.upload_content, name="upload_content"),
    path("generate_quiz/", views.generate_quiz, name="generate_quiz"),
    path("get_all_lessons/", views.get_all_lessons, name="get_all_lessons"),
    path("", views.home, name="home"),
    path('delete_lesson/', views.delete_lesson, name='delete_lesson'),
    path('get_lesson_detail/', views.get_lesson_detail, name='get_lesson_detail'),
]
