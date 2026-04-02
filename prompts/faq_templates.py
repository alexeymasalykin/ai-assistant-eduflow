from __future__ import annotations

FAQ_TEMPLATES: dict[str, str] = {
    "greeting": (
        "Добро пожаловать в EduFlow! Рада вас видеть. "
        "Чем я могу вам помочь?"
    ),
    "thanks": (
        "Спасибо за вашу благодарность! Рады помочь. "
        "Если у вас еще есть вопросы, я всегда здесь."
    ),
    "working_hours": (
        "Служба поддержки EduFlow работает ежедневно с 9:00 до 21:00 по московскому времени. "
        "Вы также можете написать нам в любое время — мы ответим в рабочие часы."
    ),
    "contact": (
        "Вы можете связаться с нами через этот чат, по email support@eduflow.ru "
        "или по телефону 8-800-XXX-XX-XX (бесплатно по России)."
    ),
    "refund_policy": (
        "Возврат средств возможен в течение 14 дней с момента оплаты, "
        "если вы прошли не более 20% курса. Для оформления возврата "
        "свяжитесь с вашим менеджером."
    ),
}


def get_faq_response(category: str) -> str | None:
    """Return FAQ template response or None if not found."""
    return FAQ_TEMPLATES.get(category)
