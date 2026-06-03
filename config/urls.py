"""
config/urls.py
"""

from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView

from courses.views import CourseListView, AfbgView

urlpatterns = [
    path("admin/",     admin.site.urls),
    path("",           CourseListView.as_view(),                                   name="course-list"),
    path("about/",     TemplateView.as_view(template_name="pages/about.html"),     name="about"),
    path("afbg/",      AfbgView.as_view(),                                         name="afbg"),
    path("imprint/",   TemplateView.as_view(template_name="pages/imprint.html"),   name="impressum"),
]