# 初始化 skills 套件並自動載入所有內建技能
from skills.registry import registry, skill
import skills.file_skills
import skills.web_skills
import skills.mail_skills
import skills.image_skills
import skills.google_drive_skills

__all__ = ["registry", "skill"]
