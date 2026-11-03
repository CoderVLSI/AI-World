"""Material properties and the deterministic physical relations built on them.

Nothing here names a product ("axe", "fire-starter", "wheel").  Outcomes are
derived from properties such as hardness, toughness, tensile strength, fracture
behaviour, moisture and thermal mass, so whether a structure is useful depends
on how it was made and how it performs when tested.

Units are deliberately simple and documented in docs/AUTONOMY_ARCHITECTURE.md:
mass in grams, temperatures in Celsius, hardness on a Mohs-like 1-10 scale, and
strength/toughness on 0-100 relative scales.  These are experiment parameters,
not engineering data.
"""
import math

# Properties per resource kind.  ``harvest`` names the working motion that
# makes gathering more efficient (see experiments.performance).
MATERIALS = {
    "wood": dict(unit_g=2000, density=0.6, hardness=2.5, toughness=55, tensile=50, flexibility=45,
                 fracture="splintery", ignition_c=300, char_c=250, fuel_mj_kg=16.0, specific_heat=1.7,
                 porous=True, moisture0=0.25, friction=0.5, shock_c=None, color="brown", harvest="chop"),
    "stone": dict(unit_g=3000, density=2.6, hardness=6.5, toughness=25, tensile=8, flexibility=0,
                  fracture="conchoidal", ignition_c=None, char_c=None, fuel_mj_kg=0.0, specific_heat=0.8,
                  porous=False, moisture0=0.02, friction=0.4, shock_c=220, color="grey", harvest="pound"),
    "plant_fiber": dict(unit_g=200, density=0.3, hardness=1.0, toughness=30, tensile=70, flexibility=95,
                        fracture="fibrous", ignition_c=250, char_c=200, fuel_mj_kg=15.0, specific_heat=1.4,
                        porous=True, moisture0=0.15, friction=0.3, shock_c=None, color="straw", harvest="cut"),
    "clay": dict(unit_g=2500, density=1.8, hardness=1.5, toughness=10, tensile=3, flexibility=15,
                 fracture="granular", ignition_c=None, char_c=None, fuel_mj_kg=0.0, specific_heat=0.9,
                 porous=True, moisture0=0.30, friction=0.6, shock_c=180, color="ochre", harvest="dig",
                 fires_at_c=500),
    "sand": dict(unit_g=2500, density=1.6, hardness=7.0, toughness=1, tensile=0, flexibility=0,
                 fracture="granular", ignition_c=None, char_c=None, fuel_mj_kg=0.0, specific_heat=0.8,
                 porous=False, moisture0=0.03, friction=0.7, shock_c=None, color="pale", harvest="dig"),
    "iron_ore": dict(unit_g=3000, density=4.5, hardness=5.5, toughness=20, tensile=6, flexibility=0,
                     fracture="granular", ignition_c=None, char_c=None, fuel_mj_kg=0.0, specific_heat=0.65,
                     porous=False, moisture0=0.02, friction=0.4, shock_c=250, color="rust", harvest="pound"),
    "copper_ore": dict(unit_g=3000, density=4.0, hardness=3.5, toughness=18, tensile=7, flexibility=2,
                       fracture="granular", ignition_c=None, char_c=None, fuel_mj_kg=0.0, specific_heat=0.7,
                       porous=False, moisture0=0.02, friction=0.4, shock_c=250, color="green", harvest="pound"),
    "coal": dict(unit_g=1500, density=1.4, hardness=2.0, toughness=8, tensile=3, flexibility=0,
                 fracture="granular", ignition_c=400, char_c=None, fuel_mj_kg=28.0, specific_heat=1.3,
                 porous=False, moisture0=0.05, friction=0.3, shock_c=None, color="black", harvest="pound"),
    "salt": dict(unit_g=1500, density=2.1, hardness=2.5, toughness=6, tensile=2, flexibility=0,
                 fracture="granular", ignition_c=None, char_c=None, fuel_mj_kg=0.0, specific_heat=0.9,
                 porous=False, moisture0=0.01, friction=0.4, shock_c=None, color="white", harvest="dig"),
    "herbs": dict(unit_g=200, density=0.25, hardness=1.0, toughness=8, tensile=12, flexibility=80,
                  fracture="fibrous", ignition_c=280, char_c=220, fuel_mj_kg=14.0, specific_heat=3.0,
                  porous=True, moisture0=0.6, friction=0.2, shock_c=None, color="green", harvest="cut"),
    "fruit": dict(unit_g=300, density=0.9, hardness=1.0, toughness=5, tensile=4, flexibility=40,
                  fracture="fibrous", ignition_c=None, char_c=None, fuel_mj_kg=0.0, specific_heat=3.6,
                  porous=True, moisture0=0.8, friction=0.2, shock_c=None, color="red", harvest="pick"),
    "food": dict(unit_g=400, density=0.9, hardness=1.0, toughness=8, tensile=6, flexibility=40,
                 fracture="fibrous", ignition_c=None, char_c=None, fuel_mj_kg=0.0, specific_heat=3.0,
                 porous=True, moisture0=0.6, friction=0.2, shock_c=None, color="tan", harvest="pick"),
    "grain": dict(unit_g=400, density=0.8, hardness=2.0, toughness=6, tensile=10, flexibility=20,
                  fracture="granular", ignition_c=320, char_c=260, fuel_mj_kg=15.0, specific_heat=1.8,
                  porous=True, moisture0=0.15, friction=0.4, shock_c=None, color="gold", harvest="cut"),
    "fish": dict(unit_g=500, density=1.0, hardness=1.0, toughness=10, tensile=8, flexibility=50,
                 fracture="fibrous", ignition_c=None, char_c=None, fuel_mj_kg=0.0, specific_heat=3.4,
                 porous=True, moisture0=0.75, friction=0.1, shock_c=None, color="silver", harvest="pick"),
    "ash": dict(unit_g=100, density=0.6, hardness=1.0, toughness=2, tensile=0, flexibility=0,
                fracture="granular", ignition_c=None, char_c=None, fuel_mj_kg=0.0, specific_heat=0.8,
                porous=False, moisture0=0.0, friction=0.3, shock_c=None, color="pale grey", harvest="none"),
    "water": dict(unit_g=1000, density=1.0, hardness=0.0, toughness=0, tensile=0, flexibility=100,
                  fracture="none", ignition_c=None, char_c=None, fuel_mj_kg=0.0, specific_heat=4.2,
                  porous=False, moisture0=1.0, friction=0.0, shock_c=None, color="clear", harvest="contain",
                  liquid=True),
}
ASH_FRACTION = 0.02            # mass left as ash when organic matter burns completely
CHAR_MASS_LOSS = 0.25          # volatile and water fraction lost when wood is fully charred
AIR_COUPLING_W_K = 1.0         # heat transfer to still air
FIRE_COUPLING_W_K = 2.0        # heat transfer from an open fire to a piece resting in it
FIRE_TEMPERATURE_C = 600.0
FIRE_POWER_W = 1500.0          # heat output of a small open fire
SUN_BONUS_C = 22.0             # daytime surface warming above air temperature


def props(material):
    return MATERIALS[material]


def clamp(value, low, high):
    return max(low, min(high, value))


def time_constant_hours(mass_g, specific_heat, coupling_w_k):
    """Lumped-capacity thermal time constant of a piece."""
    return max(1e-3, mass_g * specific_heat / coupling_w_k / 3600.0)


def approach(current, target, hours, tau_hours):
    """Newtonian relaxation of a temperature (or any lumped quantity) toward ``target``."""
    return target - (target - current) * math.exp(-hours / tau_hours)


def fracture_edge_sharpness(material, quality, hardness_ratio):
    """Sharpness (0-100) of a fresh fracture surface.

    Fine-grained brittle stone fractures conchoidally and keeps a keen edge;
    fibrous or granular material does not.  A much softer striker leaves a
    blunter break.
    """
    kind = props(material)["fracture"]
    if kind == "conchoidal":
        base = 10 + 80 * quality ** 1.5   # coarse stone breaks dull; fine stone breaks keen
    elif kind == "splintery":
        base = 12 + 18 * quality
    elif kind == "granular":
        base = 4 + 6 * quality
    else:
        base = 0.0
    return round(base * clamp(0.6 + 0.4 * hardness_ratio, 0.6, 1.0), 2)


def friction_ignition_rise_c(force, minutes, mu, dryness):
    """Surface temperature rise from rubbing, in Celsius above ambient."""
    return 14.0 * force * math.sqrt(minutes) * mu * dryness


def dryness_factor(moisture):
    """1.0 when dry (<= 0.10 moisture), falling as the material gets wetter."""
    return clamp(1.0 - 2.5 * max(0.0, moisture - 0.10), 0.0, 1.0)


def grain_label(quality):
    return "fine" if quality > 0.66 else "medium" if quality > 0.33 else "coarse"
