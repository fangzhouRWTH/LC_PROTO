from __future__ import annotations

import random
from dataclasses import dataclass, replace
from math import pi, sin
from pathlib import Path
from typing import Literal

from ..assets import DEFAULT_SKY_DIR, DEFAULT_SKY_TEXTURE


Color3 = tuple[float, float, float]
Vector3 = tuple[float, float, float]
WeatherName = Literal["sunny", "rain", "overcast", "foggy", "storm"]

_RNG = random.SystemRandom()
_SKY_TEXTURE_EXTENSIONS = {
    ".bmp",
    ".exr",
    ".hdr",
    ".jpeg",
    ".jpg",
    ".png",
    ".tga",
    ".tif",
    ".tiff",
}
_DAYTIME_ALIASES = {
    "dawn": "morning",
    "daytime": "day",
    "dusk": "sunset",
    "evening": "sunset",
    "midday": "noon",
}


@dataclass(frozen=True)
class WeatherLightAnimation:
    """Low-frequency lighting variation for a weather preset."""

    enabled: bool = True
    period_seconds: float = 240.0
    time_scale: float = 1.0
    sun_intensity_amplitude: float = 0.04
    sky_intensity_amplitude: float = 0.03
    sky_exposure_amplitude: float = 0.04
    fill_intensity_amplitude: float = 0.03
    sun_rotation_amplitude: Vector3 = (1.0, 0.0, 1.5)

    def validate(self) -> None:
        if self.period_seconds <= 0.0:
            raise ValueError("WeatherLightAnimation.period_seconds must be positive.")
        if self.time_scale < 0.0:
            raise ValueError("WeatherLightAnimation.time_scale cannot be negative.")


@dataclass(frozen=True)
class WeatherLightingConfig:
    """USD light setup for weather and time-of-day lighting."""

    name: str = "sunny"
    root_path: str = "/World/VFX/WeatherLighting"
    sky_texture_path: str | Path | None = DEFAULT_SKY_TEXTURE
    sun_intensity: float = 1200.0
    sun_angle: float = 0.8
    sun_color: Color3 = (1.0, 0.96, 0.88)
    sun_rotation: Vector3 = (-45.0, 0.0, 35.0)
    sky_intensity: float = 300.0
    sky_exposure: float = 1.0
    sky_color: Color3 = (0.78, 0.86, 1.0)
    fill_enabled: bool = True
    fill_intensity: float = 120.0
    fill_angle: float = 5.0
    fill_color: Color3 = (0.75, 0.82, 1.0)
    fill_rotation: Vector3 = (-25.0, 0.0, -145.0)
    animation: WeatherLightAnimation = WeatherLightAnimation()

    def validate(self) -> None:
        if not self.root_path.startswith("/"):
            raise ValueError("WeatherLightingConfig.root_path must be absolute.")
        if self.sun_intensity < 0.0:
            raise ValueError("WeatherLightingConfig.sun_intensity cannot be negative.")
        if self.sky_intensity < 0.0:
            raise ValueError("WeatherLightingConfig.sky_intensity cannot be negative.")
        if self.fill_intensity < 0.0:
            raise ValueError("WeatherLightingConfig.fill_intensity cannot be negative.")
        self.animation.validate()


_PRESETS: dict[str, WeatherLightingConfig] = {
    "sunny": WeatherLightingConfig(
        name="sunny",
        sun_intensity=1200.0,
        sun_angle=0.8,
        sun_color=(1.0, 0.96, 0.88),
        sun_rotation=(-45.0, 0.0, 35.0),
        sky_intensity=300.0,
        sky_exposure=1.0,
        sky_color=(0.78, 0.86, 1.0),
        fill_intensity=120.0,
        fill_color=(0.75, 0.82, 1.0),
        animation=WeatherLightAnimation(
            period_seconds=300.0,
            sun_intensity_amplitude=0.03,
            sky_intensity_amplitude=0.02,
            sky_exposure_amplitude=0.03,
            fill_intensity_amplitude=0.02,
            sun_rotation_amplitude=(0.8, 0.0, 1.2),
        ),
    ),
    "rain": WeatherLightingConfig(
        name="rain",
        sun_intensity=220.0,
        sun_angle=4.5,
        sun_color=(0.70, 0.76, 0.84),
        sun_rotation=(-58.0, 0.0, 25.0),
        sky_intensity=190.0,
        sky_exposure=0.15,
        sky_color=(0.52, 0.59, 0.68),
        fill_intensity=55.0,
        fill_angle=8.0,
        fill_color=(0.56, 0.64, 0.76),
        fill_rotation=(-20.0, 0.0, -150.0),
        animation=WeatherLightAnimation(
            period_seconds=75.0,
            sun_intensity_amplitude=0.18,
            sky_intensity_amplitude=0.10,
            sky_exposure_amplitude=0.08,
            fill_intensity_amplitude=0.12,
            sun_rotation_amplitude=(1.5, 0.0, 2.0),
        ),
    ),
    "overcast": WeatherLightingConfig(
        name="overcast",
        sun_intensity=320.0,
        sun_angle=6.0,
        sun_color=(0.78, 0.82, 0.88),
        sun_rotation=(-52.0, 0.0, 30.0),
        sky_intensity=240.0,
        sky_exposure=0.35,
        sky_color=(0.62, 0.68, 0.76),
        fill_intensity=80.0,
        fill_angle=8.0,
        fill_color=(0.62, 0.69, 0.80),
        animation=WeatherLightAnimation(
            period_seconds=160.0,
            sun_intensity_amplitude=0.08,
            sky_intensity_amplitude=0.06,
            sky_exposure_amplitude=0.05,
            fill_intensity_amplitude=0.05,
            sun_rotation_amplitude=(1.0, 0.0, 1.0),
        ),
    ),
    "foggy": WeatherLightingConfig(
        name="foggy",
        sun_intensity=160.0,
        sun_angle=8.0,
        sun_color=(0.72, 0.76, 0.80),
        sun_rotation=(-48.0, 0.0, 20.0),
        sky_intensity=180.0,
        sky_exposure=0.05,
        sky_color=(0.66, 0.70, 0.74),
        fill_intensity=95.0,
        fill_angle=10.0,
        fill_color=(0.66, 0.70, 0.76),
        animation=WeatherLightAnimation(
            period_seconds=210.0,
            sun_intensity_amplitude=0.05,
            sky_intensity_amplitude=0.04,
            sky_exposure_amplitude=0.03,
            fill_intensity_amplitude=0.03,
            sun_rotation_amplitude=(0.8, 0.0, 0.8),
        ),
    ),
    "storm": WeatherLightingConfig(
        name="storm",
        sun_intensity=90.0,
        sun_angle=6.5,
        sun_color=(0.52, 0.58, 0.66),
        sun_rotation=(-60.0, 0.0, 20.0),
        sky_intensity=130.0,
        sky_exposure=-0.10,
        sky_color=(0.38, 0.44, 0.54),
        fill_intensity=35.0,
        fill_angle=9.0,
        fill_color=(0.44, 0.50, 0.62),
        fill_rotation=(-18.0, 0.0, -155.0),
        animation=WeatherLightAnimation(
            period_seconds=48.0,
            sun_intensity_amplitude=0.25,
            sky_intensity_amplitude=0.16,
            sky_exposure_amplitude=0.10,
            fill_intensity_amplitude=0.18,
            sun_rotation_amplitude=(1.8, 0.0, 2.5),
        ),
    ),
}

_ALIASES = {
    "clear": "sunny",
    "day": "sunny",
    "sun": "sunny",
    "sunny": "sunny",
    "rain": "rain",
    "rainy": "rain",
    "storm": "storm",
    "stormy": "storm",
    "overcast": "overcast",
    "cloudy": "overcast",
    "fog": "foggy",
    "foggy": "foggy",
}


def available_weather_names() -> tuple[str, ...]:
    return tuple(sorted(_PRESETS))


def available_daytime_names() -> tuple[str, ...]:
    names: set[str] = set()
    for weather_key in _PRESETS:
        for texture_path in _list_sky_textures(weather_key):
            names.update(_daytime_tokens_for_path(weather_key, texture_path))
    return tuple(sorted(names))


def resolve_weather_config(
    weather: str | None = None,
    *,
    daytime: str | None = None,
    sky_texture_path: str | Path | None = None,
    sun_intensity: float | None = None,
    sky_intensity: float | None = None,
    sky_exposure: float | None = None,
    time_scale: float | None = None,
) -> WeatherLightingConfig:
    daytime_key = _canonical_daytime(daytime)
    key = _resolve_weather_key(weather)
    config = _PRESETS[key]
    overrides = {
        "sky_texture_path": _select_sky_texture(
            key,
            daytime=daytime_key,
            sky_texture_path=sky_texture_path,
        )
    }
    if sun_intensity is not None:
        overrides["sun_intensity"] = float(sun_intensity)
    if sky_intensity is not None:
        overrides["sky_intensity"] = float(sky_intensity)
    if sky_exposure is not None:
        overrides["sky_exposure"] = float(sky_exposure)
    if time_scale is not None:
        overrides["animation"] = replace(
            config.animation,
            time_scale=float(time_scale),
        )
    config = replace(config, **overrides)
    config.validate()
    return config


def _clean_key(value: str | None) -> str | None:
    if value is None:
        return None
    key = str(value).strip().lower()
    return key or None


def _canonical_daytime(daytime: str | None) -> str | None:
    key = _clean_key(daytime)
    if key is None:
        return None
    return _DAYTIME_ALIASES.get(key, key)


def _resolve_weather_key(weather: str | None) -> str:
    requested = _clean_key(weather)
    if requested is not None:
        key = _ALIASES.get(requested)
        if key is None:
            valid = ", ".join(sorted(_ALIASES))
            raise ValueError(
                f"Unsupported weather {weather!r}. Expected one of: {valid}."
        )
        return key

    return _RNG.choice(tuple(sorted(_PRESETS)))


def _select_sky_texture(
    weather_key: str,
    *,
    daytime: str | None,
    sky_texture_path: str | Path | None,
) -> str | Path | None:
    if sky_texture_path is not None:
        return sky_texture_path

    candidates = _list_sky_textures(weather_key)
    if daytime is not None:
        daytime_candidates = _matching_daytime_textures(weather_key, daytime)
        if daytime_candidates:
            candidates = daytime_candidates

    if candidates:
        return _RNG.choice(candidates)
    if DEFAULT_SKY_TEXTURE.exists():
        return DEFAULT_SKY_TEXTURE
    return None


def _list_sky_textures(weather_key: str) -> tuple[Path, ...]:
    sky_dir = DEFAULT_SKY_DIR / weather_key
    if not sky_dir.is_dir():
        return ()
    return tuple(
        sorted(
            path
            for path in sky_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in _SKY_TEXTURE_EXTENSIONS
        )
    )


def _matching_daytime_textures(weather_key: str, daytime: str) -> tuple[Path, ...]:
    return tuple(
        path
        for path in _list_sky_textures(weather_key)
        if daytime in _daytime_tokens_for_path(weather_key, path)
    )


def _daytime_tokens_for_path(weather_key: str, texture_path: Path) -> set[str]:
    weather_dir = DEFAULT_SKY_DIR / weather_key
    try:
        relative_path = texture_path.relative_to(weather_dir)
    except ValueError:
        relative_path = texture_path

    tokens = set()
    if len(relative_path.parts) > 1:
        parent = _canonical_daytime(relative_path.parts[0])
        if parent is not None:
            tokens.add(parent)

    stem = texture_path.stem.lower()
    stem_token = _canonical_daytime(stem)
    if stem_token is not None:
        tokens.add(stem_token)

    for separator in ("_", "-"):
        if separator in stem:
            prefix_token = _canonical_daytime(stem.split(separator, 1)[0])
            if prefix_token is not None:
                tokens.add(prefix_token)

    return tokens


class WeatherLightingManager:
    """Applies and updates weather-controlled USD lighting."""

    def __init__(
        self,
        config: WeatherLightingConfig,
        *,
        start_time_seconds: float = 0.0,
    ):
        config.validate()
        self.config = config
        self.time_seconds = float(start_time_seconds)
        self._stage = None
        self._sun_rotate_op = None
        self._fill_rotate_op = None

    @classmethod
    def from_weather(
        cls,
        weather: str | None = None,
        *,
        daytime: str | None = None,
        sky_texture_path: str | Path | None = None,
        sun_intensity: float | None = None,
        sky_intensity: float | None = None,
        sky_exposure: float | None = None,
        time_scale: float | None = None,
        start_time_seconds: float = 0.0,
    ) -> "WeatherLightingManager":
        return cls(
            resolve_weather_config(
                weather,
                daytime=daytime,
                sky_texture_path=sky_texture_path,
                sun_intensity=sun_intensity,
                sky_intensity=sky_intensity,
                sky_exposure=sky_exposure,
                time_scale=time_scale,
            ),
            start_time_seconds=start_time_seconds,
        )

    def apply(self, stage) -> None:
        self._stage = stage
        self._define_light_prims(stage)
        self._apply_sample(self.time_seconds)
        print(
            f"[OK] Applied {self.config.name!r} weather lighting "
            f"with sky {str(self.config.sky_texture_path)!r}."
        )

    def update(self, dt: float) -> None:
        if self._stage is None or not self.config.animation.enabled:
            return
        self.time_seconds += max(0.0, float(dt)) * self.config.animation.time_scale
        self._apply_sample(self.time_seconds)

    def _define_light_prims(self, stage) -> None:
        context = _get_isaac_context()
        UsdGeom = context.pxr_usd_geom
        UsdLux = context.pxr_usd_lux
        Sdf = context.pxr_Sdf

        root = UsdGeom.Xform.Define(stage, self.config.root_path)
        root.GetPrim().SetActive(True)

        sun = UsdLux.DistantLight.Define(stage, f"{self.config.root_path}/Sun")
        sun.GetPrim().SetActive(True)
        sun.CreateAngleAttr().Set(float(self.config.sun_angle))
        sun.CreateColorAttr().Set(self._gf_vec3f(self.config.sun_color))
        self._sun_rotate_op = self._reset_rotate_op(
            UsdGeom.Xformable(sun.GetPrim())
        )

        sky = UsdLux.DomeLight.Define(stage, f"{self.config.root_path}/Sky")
        sky.GetPrim().SetActive(True)
        sky.CreateColorAttr().Set(self._gf_vec3f(self.config.sky_color))
        self._set_sky_texture(sky, Sdf)

        fill = UsdLux.DistantLight.Define(stage, f"{self.config.root_path}/Fill")
        fill.GetPrim().SetActive(bool(self.config.fill_enabled))
        fill.CreateAngleAttr().Set(float(self.config.fill_angle))
        fill.CreateColorAttr().Set(self._gf_vec3f(self.config.fill_color))
        self._fill_rotate_op = self._reset_rotate_op(
            UsdGeom.Xformable(fill.GetPrim())
        )

    def _apply_sample(self, time_seconds: float) -> None:
        if self._stage is None:
            return

        context = _get_isaac_context()
        UsdLux = context.pxr_usd_lux
        phase = self._phase(time_seconds)
        sample = self._sample(phase)

        sun = UsdLux.DistantLight(
            self._stage.GetPrimAtPath(f"{self.config.root_path}/Sun")
        )
        sky = UsdLux.DomeLight(
            self._stage.GetPrimAtPath(f"{self.config.root_path}/Sky")
        )
        fill = UsdLux.DistantLight(
            self._stage.GetPrimAtPath(f"{self.config.root_path}/Fill")
        )

        sun.GetIntensityAttr().Set(sample["sun_intensity"])
        sky.GetIntensityAttr().Set(sample["sky_intensity"])
        sky.GetExposureAttr().Set(sample["sky_exposure"])
        fill.GetIntensityAttr().Set(sample["fill_intensity"])

        if self._sun_rotate_op is not None:
            self._sun_rotate_op.Set(self._gf_vec3f(sample["sun_rotation"]))
        if self._fill_rotate_op is not None:
            self._fill_rotate_op.Set(self._gf_vec3f(self.config.fill_rotation))

    def _sample(self, phase: float) -> dict[str, float | Vector3]:
        animation = self.config.animation
        sun_wave = sin(phase)
        sky_wave = sin(phase + pi * 0.35)
        exposure_wave = sin(phase + pi * 0.7)

        return {
            "sun_intensity": self._vary(
                self.config.sun_intensity,
                animation.sun_intensity_amplitude,
                sun_wave,
            ),
            "sky_intensity": self._vary(
                self.config.sky_intensity,
                animation.sky_intensity_amplitude,
                sky_wave,
            ),
            "sky_exposure": self.config.sky_exposure
            + animation.sky_exposure_amplitude * exposure_wave,
            "fill_intensity": self._vary(
                self.config.fill_intensity,
                animation.fill_intensity_amplitude,
                sky_wave,
            ),
            "sun_rotation": self._vary_rotation(
                self.config.sun_rotation,
                animation.sun_rotation_amplitude,
                sun_wave,
            ),
        }

    def _phase(self, time_seconds: float) -> float:
        return (float(time_seconds) / self.config.animation.period_seconds) * 2.0 * pi

    def _vary(self, base_value: float, amplitude: float, wave: float) -> float:
        return max(0.0, float(base_value) * (1.0 + float(amplitude) * float(wave)))

    def _vary_rotation(
        self,
        base: Vector3,
        amplitude: Vector3,
        wave: float,
    ) -> Vector3:
        return (
            float(base[0]) + float(amplitude[0]) * float(wave),
            float(base[1]) + float(amplitude[1]) * float(wave),
            float(base[2]) + float(amplitude[2]) * float(wave),
        )

    def _set_sky_texture(self, sky, Sdf) -> None:
        if self.config.sky_texture_path is None:
            return

        sky_texture_path = Path(self.config.sky_texture_path).expanduser()
        if not sky_texture_path.is_absolute():
            sky_texture_path = Path.cwd() / sky_texture_path
        sky_texture_path = sky_texture_path.resolve()
        if not sky_texture_path.exists():
            raise FileNotFoundError(f"Sky texture not found: {sky_texture_path}")

        sky.CreateTextureFileAttr().Set(Sdf.AssetPath(str(sky_texture_path)))
        sky.CreateTextureFormatAttr().Set("latlong")

    def _reset_rotate_op(self, xformable):
        xformable.ClearXformOpOrder()
        return xformable.AddRotateXYZOp()

    def _gf_vec3f(self, value: Vector3 | Color3):
        Gf = _get_isaac_context().pxr_gf
        return Gf.Vec3f(float(value[0]), float(value[1]), float(value[2]))


def _get_isaac_context():
    from ..isaac_adaptor import isaac_context as iscctx

    return iscctx.get_isaac_context()
