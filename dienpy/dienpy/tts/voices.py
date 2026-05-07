"""List available English voices."""

from ._core import AF_VOICES, AM_VOICES, BF_VOICES, BM_VOICES


def main() -> None:
    print(f"American female: {', '.join(AF_VOICES)}")
    print(f"American male:   {', '.join(AM_VOICES)}")
    print(f"British female:  {', '.join(BF_VOICES)}")
    print(f"British male:    {', '.join(BM_VOICES)}")
