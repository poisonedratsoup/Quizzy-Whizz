from django.db import models

class StudyGuide(models.Model):
    subject = models.CharField(max_length=255)
    content = models.JSONField() 
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.subject
