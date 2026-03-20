from django.contrib import admin
from .models import Topic, SubTopic


class SubTopicInline(admin.TabularInline):
    model = SubTopic
    extra = 1


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at", "updated_at")
    inlines = [SubTopicInline]


@admin.register(SubTopic)
class SubTopicAdmin(admin.ModelAdmin):
    list_display = ("name", "topic", "weight", "updated_at")
    list_filter = ("topic",)
