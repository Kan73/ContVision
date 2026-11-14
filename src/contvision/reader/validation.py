import re


def clean_text(text):

    text = text.upper()

    # Eliminar espacios y caracteres no alfanuméricos
    text = re.sub(
        r"[^A-Z0-9]",
        "",
        text
    )

    return text


def validate_container_id(text):

    text = clean_text(text)

    pattern = r"^[A-Z]{3}[UJZ][0-9]{7}$"

    return bool(
        re.match(pattern, text)
    )


def calculate_check_digit(container_id):

    values = {
        letter: value
        for value, letter in enumerate("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    }

    total = 0

    for index, char in enumerate(container_id[:10]):

        value = (
            int(char)
            if char.isdigit()
            else values[char]
        )

        total += value * (2 ** index)

    remainder = total % 11

    return remainder % 10


def validate_iso6346(text):

    text = clean_text(text)

    if not validate_container_id(text):
        return False

    expected_digit = calculate_check_digit(text)

    actual_digit = int(text[-1])

    return expected_digit == actual_digit