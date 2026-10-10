"""Metadata and routing registry for JARVIS capabilities."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable

SkillHandler = Callable[[str], str | None]


@dataclass(frozen=True)
class SkillDefinition:
    skill_id: str
    name: str
    description: str
    triggers: tuple[str, ...] = ()
    confirmation_required: bool = False
    handler: SkillHandler | None = None


class SkillRegistry:
    """Register, discover, and dispatch explicitly named JARVIS skills."""

    def __init__(self):
        self._skills: dict[str, SkillDefinition] = {}

    def register(self, skill: SkillDefinition) -> None:
        if not skill.skill_id.strip():
            raise ValueError("Beceri kimliği boş olamaz.")
        if skill.skill_id in self._skills:
            raise ValueError(f"Beceri zaten kayıtlı: {skill.skill_id}")
        self._skills[skill.skill_id] = skill

    def get(self, skill_id: str) -> SkillDefinition | None:
        return self._skills.get(skill_id)

    def bind(self, skill_id: str, handler: SkillHandler) -> None:
        skill = self._skills.get(skill_id)
        if skill is None:
            raise KeyError(f"Kayıtlı olmayan beceri: {skill_id}")
        self._skills[skill_id] = replace(skill, handler=handler)

    def all(self) -> tuple[SkillDefinition, ...]:
        return tuple(self._skills.values())

    def match(self, request: str) -> tuple[SkillDefinition, ...]:
        normalized = " ".join((request or "").casefold().split())
        return tuple(
            skill
            for skill in self._skills.values()
            if any(trigger.casefold() in normalized for trigger in skill.triggers)
        )

    def dispatch(self, skill_id: str, request: str) -> str | None:
        skill = self._skills.get(skill_id)
        if skill is None:
            raise KeyError(f"Kayıtlı olmayan beceri: {skill_id}")
        if skill.handler is None:
            return None
        return skill.handler(request)


def create_builtin_skill_registry() -> SkillRegistry:
    """Describe built-in capabilities; app wiring supplies executable handlers."""
    registry = SkillRegistry()
    definitions = (
        SkillDefinition(
            "conversation", "Sohbet ve bilgi",
            "Groq/Gemini yönlendirmesi, güncel bilgi araması ve kaynaklı yanıtlar.",
            ("selam", "nedir", "güncel", "internette ara"),
        ),
        SkillDefinition(
            "research", "Web araştırması",
            "Kaynakları toplayıp yapılandırılmış araştırma raporu hazırlar.",
            ("araştır", "research", "kaynakları incele"),
        ),
        SkillDefinition(
            "presentation", "Sunum hazırlama",
            "Konuya göre slayt dosyası oluşturur.",
            ("sunum hazırla", "sunum oluştur", "slayt hazırla"),
        ),
        SkillDefinition(
            "file_conversion", "Dosya dönüştürme",
            "Desteklenen belge ve görsel biçimlerini dönüştürür.",
            ("pdf yap", "png yap", "dönüştür", "donustur", "çevir"),
        ),
        SkillDefinition(
            "computer_control", "Bilgisayar kontrolü",
            "Uygulama, pencere ve web işlemlerini ATLAS üzerinden yürütür.",
            ("chrome'u aç", "tıkla", "klavyeye yaz"),
            confirmation_required=True,
        ),
        SkillDefinition(
            "file_mutation", "Dosya değişiklikleri",
            "Dosya düzenleme, silme ve geri alma işlemlerini yönetir.",
            ("dosya düzenle", "dosya sil", "geri al dosya"),
            confirmation_required=True,
        ),
        SkillDefinition(
            "messaging", "Mesaj ve e-posta",
            "Kullanıcının isteğiyle dışarıya ileti gönderir.",
            ("whatsapp", "mesaj gönder", "e-posta gönder"),
            confirmation_required=True,
        ),
        SkillDefinition(
            "local_memory", "Yerel bellek",
            "Profil, kullanıcı notları ve Atlas belge hafızasını yönetir.",
            (
                "hafızaya ekle", "hafızada ara", "profilim", "not ekle",
                "sohbet geçmişinde ara", "sohbet gecmisinde ara",
            ),
        ),
        SkillDefinition(
            "backup_restore", "Yedekleme ve geri yükleme",
            "Kullanıcı verilerini doğrulanmış arşivlerle yedekler ve geri yükler.",
            ("verileri yedekle", "yedekten geri yükle"),
            confirmation_required=True,
        ),
        SkillDefinition(
            "diagnostics", "Tanılama",
            "API anahtarlarını göstermeden yapılandırma ve bileşen durumunu denetler.",
            ("uygulama tanılaması", "sistem durumu"),
        ),
        SkillDefinition(
            "scheduled_routines", "Zamanlanmış rutinler",
            "Günlük brifing gibi yerel rutinleri oluşturur ve yönetir.",
            ("rutinleri göster", "her gün saat"),
        ),
    )
    for definition in definitions:
        registry.register(definition)
    return registry
