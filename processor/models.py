from django.db import models


class Subject(models.Model):
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)


class Topic(models.Model):
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name="topics"
    )
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)


class SubTopic(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name="subtopics")
    name = models.CharField(max_length=255)
    content = models.TextField()
    weight = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
