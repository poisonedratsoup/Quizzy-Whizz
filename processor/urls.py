from django.urls import path
from . import views

urlpatterns = [
    path('get_metadata/', views.get_metadata, name='get_metadata'),
    path('upload_content/', views.upload_content, name='upload_content'),
]