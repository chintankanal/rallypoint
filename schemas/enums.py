from enum import Enum


class UserRole(str, Enum):
    PLAYER = "PLAYER"
    COACH = "COACH"
    ADMIN = "ADMIN"
    REFEREE = "REFEREE"
    UMPIRE = "UMPIRE"


class AcademyStatus(str, Enum):
    ACTIVE = "ACTIVE"
    FROZEN = "FROZEN"
    INACTIVE = "INACTIVE"


class PlayerStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"


class SeedingLevel(str, Enum):
    UNSEEDED = "UNSEEDED"
    DISTRICT = "DISTRICT"
    STATE = "STATE"
    NATIONAL = "NATIONAL"


class SeasonStatus(str, Enum):
    UPCOMING = "UPCOMING"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"


class EventType(str, Enum):
    LEAGUE = "LEAGUE"
    FRIENDLY = "FRIENDLY"
    TOURNAMENT_EXTERNAL = "TOURNAMENT_EXTERNAL"
    TOURNAMENT_MANAGED = "TOURNAMENT_MANAGED"


class SchedulingMode(str, Enum):
    INTRA_ACADEMY = "INTRA_ACADEMY"
    INTER_ACADEMY = "INTER_ACADEMY"


class MatchFormat(str, Enum):
    BEST_OF_3 = "BEST_OF_3"
    BEST_OF_5 = "BEST_OF_5"
    BEST_OF_7 = "BEST_OF_7"


class TournamentFormat(str, Enum):
    SWISS = "SWISS"
    TIER_BANDED_KNOCKOUT = "TIER_BANDED_KNOCKOUT"
    GROUP_THEN_KNOCKOUT = "GROUP_THEN_KNOCKOUT"


class EventStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class Tier(str, Enum):
    BEGINNER = "BEGINNER"
    INTERMEDIATE = "INTERMEDIATE"
    ADVANCED = "ADVANCED"
    ELITE = "ELITE"
    NATIONAL_TRACK = "NATIONAL_TRACK"


class AgeGroup(str, Enum):
    U11 = "U11"
    U13 = "U13"
    U15 = "U15"
    U17 = "U17"


class AcademyChangeReason(str, Enum):
    INITIAL_REGISTRATION = "INITIAL_REGISTRATION"
    TRANSFER = "TRANSFER"
    CORRECTION = "CORRECTION"


class Gender(str, Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"
