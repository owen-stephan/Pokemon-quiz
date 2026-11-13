
from drafter import *
from dataclasses import dataclass
import requests
import random

hide_debug_information()
set_website_title("Your Drafter Website")
set_website_framed(False)

# --------------------------------------------------
# CONSTANTS
# --------------------------------------------------

POKE_API = "https://pokeapi.co/api/v2/"


def get_all_pokemon_names():
    """
    Gets the names of all Pokemon available through
    the PokéAPI Pokemon endpoint.

    The limit parameter requests a large page so the
    quiz can choose from the full available database.
    """

    try:
        response = requests.get(
            POKE_API + "pokemon/?limit=100000&offset=0",
            timeout=20
        )

        if response.status_code == 200:
            data = response.json()

            return [
                pokemon["name"]
                for pokemon in data["results"]
            ]

        return []

    except requests.exceptions.RequestException:
        return []


def get_all_type_names():
    """
    Retrieves the available Pokemon types directly
    from the API instead of using a hardcoded list.
    """

    try:
        response = requests.get(
            POKE_API + "type/?limit=100",
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()

            # Unknown and Shadow are special API types,
            # not standard selectable battle types.
            return [
                item["name"]
                for item in data["results"]
                if item["name"] not in ["unknown", "shadow"]
            ]

        return []

    except requests.exceptions.RequestException:
        return []


def get_type_weaknesses(type_name):
    """
    Retrieves all types that deal double damage
    against the provided Pokemon type.
    """

    try:
        response = requests.get(
            POKE_API + "type/" + type_name,
            timeout=10
        )

        if response.status_code != 200:
            return []

        data = response.json()

        weaknesses = data["damage_relations"]["double_damage_from"]

        return sorted([
            weakness["name"]
            for weakness in weaknesses
        ])

    except (requests.exceptions.RequestException, KeyError):
        return []


ALL_TYPES = [
    "normal", "fire", "water", "electric",
    "grass", "ice", "fighting", "poison",
    "ground", "flying", "psychic", "bug",
    "rock", "ghost", "dragon", "dark",
    "steel", "fairy"
]


# --------------------------------------------------
# DATACLASSES
# --------------------------------------------------

# This second dataclass stores information about
# Pokemon that the visitor has searched for.
@dataclass
class PokemonRecord:
    name: str
    types: str
    weaknesses: str


# Main website state.
# It contains more than the required four fields.

@dataclass
class State:
    pokemon_history: list
    last_search: str
    last_result: str
    quiz_kind: str
    quiz_index: int
    quiz_score: int
    quiz_feedback: str
    trainer_note: str
    quiz_questions: list



# --------------------------------------------------
# POKEMON API FUNCTIONS
# --------------------------------------------------

def get_pokemon(name):
    """
    Retrieves Pokemon information from PokeAPI.

    The requests library sends an HTTP request to the
    public API. The API returns JSON data, which is
    converted into ordinary Python dictionaries.

    This is an external API technique. It requires
    an internet connection and the requests library.
    """

    name = name.lower().strip()

    try:
        response = requests.get(
            POKE_API + "pokemon/" + name,
            timeout=10
        )

        if response.status_code != 200:
            return None

        return response.json()

    except requests.exceptions.RequestException:
        return None


def get_evolution(name):
    """
    Finds the immediate evolution of a Pokemon.

    Pokemon species data contains a link to its
    evolution chain. The function follows that link
    and searches through the chain for the Pokemon.
    """

    try:
        response = requests.get(
            POKE_API + "pokemon-species/" + name,
            timeout=10
        )

        if response.status_code != 200:
            return []

        species = response.json()

        chain_url = species["evolution_chain"]["url"]

        chain_response = requests.get(
            chain_url,
            timeout=10
        )

        if chain_response.status_code != 200:
            return []

        chain = chain_response.json()["chain"]

        # A nested evolution chain is a tree.
        # This helper searches its branches.
        def find_evolution(node, target):
            if node["species"]["name"] == target:
                return [
                    evolution["species"]["name"]
                    for evolution in node["evolves_to"]
                ]

            for evolution in node["evolves_to"]:
                result = find_evolution(evolution, target)

                if result is not None:
                    return result

            return None

        result = find_evolution(chain, name)

        if result is None:
            return []

        return result

    except (requests.exceptions.RequestException, KeyError, TypeError):
        return []


def get_weaknesses(pokemon_data):
    """
    Retrieves the weaknesses of a Pokemon.

    Each Pokemon can have one or two types.
    This function checks both types against
    the official PokeAPI damage relationships.

    A type is included if it deals super-effective
    damage against at least one of the Pokemon's
    types.
    """

    weaknesses = []

    try:
        for pokemon_type in pokemon_data["types"]:

            type_name = pokemon_type["type"]["name"]

            response = requests.get(
                POKE_API + "type/" + type_name,
                timeout=10
            )

            if response.status_code != 200:
                continue

            type_data = response.json()

            for weakness in type_data["damage_relations"][
                "double_damage_from"
            ]:

                weakness_name = weakness["name"]

                if weakness_name not in weaknesses:
                    weaknesses.append(weakness_name)

        return sorted(weaknesses)

    except (requests.exceptions.RequestException, KeyError, TypeError):
        return []


# --------------------------------------------------
# HOMEPAGE
# --------------------------------------------------

@route
def index(state: State) -> Page:

    return Page(state, [
        Header("POKEACADEMY"),
        "Welcome to PokéAcademy!",
        "Your online destination for learning about Pokemon.",
        HorizontalRule(),

        Header("Choose a Feature"),

        Button("Open the Pokedex", "pokedex"),
        Button("Pokemon Quizzes", "quiz_menu"),

        HorizontalRule(),

        Header("Your Trainer Profile"),

        "Write a note about your Pokemon journey:",
        TextArea("trainer_note", state.trainer_note),
        Button("Save Note", "save_note"),

        "Current Trainer Note: " + state.trainer_note,

        HorizontalRule(),

        Header("Recently Searched Pokemon"),

        "Pokemon you have searched for:"
    ] + [
        record.name.capitalize() + " - " + record.types
        for record in state.pokemon_history
    ] + [
        Button("Clear Search History", "clear_history")
    ])


# --------------------------------------------------
# POKEDEX PAGE
# --------------------------------------------------

@route
def pokedex(state: State) -> Page:

    return Page(state, [
        Header("Pokedex"),
        "Search for any Pokemon by its name.",
        "Examples: Pikachu, Charizard, Eevee, Mewtwo",
        HorizontalRule(),

        "Pokemon Name:",
        TextBox("pokemon_name", state.last_search),

        Button("Search Pokemon", "pokemon_search"),

        Button("Back Home", "index")
    ])


# --------------------------------------------------
# SEARCH ROUTE
# --------------------------------------------------

@route
def pokemon_search(state: State, pokemon_name: str) -> Page:

    pokemon_name = pokemon_name.lower().strip()

    state.last_search = pokemon_name

    # Check for an empty search.
    if pokemon_name == "":
        state.last_result = "Please enter a Pokemon name."

        return Page(state, [
            Header("Search Error"),
            state.last_result,
            Button("Try Again", "pokedex"),
            Button("Home", "index")
        ])

    pokemon = get_pokemon(pokemon_name)

    # Check whether the Pokemon exists.
    if pokemon is None:
        state.last_result = "Pokemon not found. Check your spelling."

        return Page(state, [
            Header("Pokemon Not Found"),
            state.last_result,
            Button("Try Again", "pokedex"),
            Button("Home", "index")
        ])

    # Get the Pokemon's types.
    types = [
        item["type"]["name"]
        for item in pokemon["types"]
    ]

    type_text = " / ".join(types)

    # Get weaknesses.
    weaknesses = get_weaknesses(pokemon)

    weakness_text = ", ".join(weaknesses)

    # Get evolution information.
    evolutions = get_evolution(pokemon_name)

    # Modify the website state.
    state.last_result = pokemon_name

    state.pokemon_history.append(
        PokemonRecord(
            pokemon_name,
            type_text,
            weakness_text
        )
    )

    # Build the Pokemon information page.
    content = [
        Header(pokemon_name.capitalize()),

        "Pokemon ID: " + str(pokemon["id"]),

        "Height: " + str(pokemon["height"] / 10) + " meters",

        "Weight: " + str(pokemon["weight"] / 10) + " kilograms",

        HorizontalRule(),

        Header("Pokemon Types"),
        type_text,

        HorizontalRule(),

        Header("Evolution Information")
    ]

    # Display evolution information.
    if len(evolutions) > 0:

        content.append(
            "This Pokemon can evolve into:"
        )

        for evolution in evolutions:
            content.append(evolution.capitalize())

    else:
        content.append(
            "This Pokemon does not evolve any further."
        )

    content.extend([
        HorizontalRule(),

        Header("Pokemon Weaknesses"),

        weakness_text if weakness_text != ""
        else "No weakness information available.",

        HorizontalRule(),

        Button("Search Another Pokemon", "pokedex"),
        Button("Home", "index")
    ])

    return Page(state, content)


# --------------------------------------------------
# QUIZ SELECTION PAGE
# --------------------------------------------------

@route
def quiz_menu(state: State) -> Page:

    state.quiz_kind = ""
    
    return Page(state, [
        Header("Pokemon Quiz Center"),

        "Choose which quiz you would like to take.",

        HorizontalRule(),

        Header("Quiz 1: Identify the Pokemon Type"),

        "You will be given the name of a Pokemon.",
        "Your job is to select its correct type.",

        Button("Start Pokemon Type Quiz", "quiz_type"),

        HorizontalRule(),

        Header("Quiz 2: Type Weaknesses"),

        "You will be given a Pokemon type.",
        "Your job is to list ALL types that are "
        "super effective against it.",

        Button("Start Type Weakness Quiz", "quiz_weakness"),

        HorizontalRule(),

        Button("Back Home", "index")
    ])


# --------------------------------------------------
# QUIZ 1: IDENTIFY THE POKEMON TYPE
# --------------------------------------------------


@route
def quiz_type(state: State) -> Page:

    # Start a new quiz when the user selects this quiz.
    if state.quiz_kind != "pokemon":

        pokemon_names = get_all_pokemon_names()

        if len(pokemon_names) < 4:
            return Page(state, [
                Header("Quiz Unavailable"),
                "Could not retrieve enough Pokemon.",
                Button("Back", "quiz_menu")
            ])

        # random.sample selects four different Pokemon.
        state.quiz_questions = random.sample(
            pokemon_names, 4
        )

        state.quiz_kind = "pokemon"
        state.quiz_index = 0
        state.quiz_score = 0
        state.quiz_feedback = ""

    if state.quiz_index >= 4:
        return quiz_results(state)

    pokemon_name = state.quiz_questions[state.quiz_index]

    return Page(state, [
        Header("Pokemon Type Quiz"),

        "Question " + str(state.quiz_index + 1) + " of 4",

        HorizontalRule(),

        "What type or types is "
        + pokemon_name.capitalize() + "?",

        "For dual types, separate your answers with commas.",

        TextBox("answer"),

        Button("Submit Answer", "submit_type_answer"),

        state.quiz_feedback,

        Button("Quit Quiz", "quiz_menu")
    ])


@route
def submit_type_answer(state: State, answer: str) -> Page:

    pokemon_name = state.quiz_questions[state.quiz_index]

    pokemon = get_pokemon(pokemon_name)

    if pokemon is None:

        state.quiz_feedback = (
            "Could not retrieve Pokemon information. "
            "Please try again."
        )

        return quiz_type(state)

    correct_types = sorted([
        item["type"]["name"]
        for item in pokemon["types"]
    ])

    # Convert the user's answer into a list.
    # Sorting means the order does not matter.
    user_types = sorted([
        item.strip().lower()
        for item in answer.split(",")
        if item.strip() != ""
    ])

    if user_types == correct_types:

        state.quiz_score += 1

        state.quiz_feedback = "Correct! Great job!"

    else:

        state.quiz_feedback = (
            "Incorrect! The correct answer was "
            + ", ".join(correct_types) + "."
        )

    state.quiz_index += 1

    if state.quiz_index >= 4:
        return quiz_results(state)

    return quiz_type(state)


# --------------------------------------------------
# QUIZ 2: IDENTIFY TYPE WEAKNESSES
# --------------------------------------------------

@route
def quiz_weakness(state: State) -> Page:

    if state.quiz_kind != "weakness":

        available_types = get_all_type_names()

        if len(available_types) < 4:
            return Page(state, [
                Header("Quiz Unavailable"),
                "Could not retrieve enough Pokemon types.",
                Button("Back", "quiz_menu")
            ])

        state.quiz_questions = random.sample(
            available_types, 4
        )

        state.quiz_kind = "weakness"
        state.quiz_index = 0
        state.quiz_score = 0
        state.quiz_feedback = ""

    if state.quiz_index >= 4:
        return quiz_results(state)

    current_type = state.quiz_questions[state.quiz_index]

    return Page(state, [
        Header("Type Weakness Quiz"),

        "Question " + str(state.quiz_index + 1) + " of 4",

        HorizontalRule(),

        "Which types are super effective against "
        + current_type.capitalize() + "?",

        "Enter ALL the correct types, separated by commas.",

        TextBox("answer"),

        Button("Submit Answer", "submit_weakness_answer"),

        state.quiz_feedback,

        Button("Quit Quiz", "quiz_menu")
    ])


@route
def submit_weakness_answer(state: State, answer: str) -> Page:

    current_type = state.quiz_questions[state.quiz_index]

    correct_answers = get_type_weaknesses(current_type)

    if len(correct_answers) == 0:

        state.quiz_feedback = (
            "Could not retrieve weakness information. "
            "Please try again."
        )

        return quiz_weakness(state)

    user_answers = sorted([
        item.strip().lower()
        for item in answer.split(",")
        if item.strip() != ""
    ])

    if user_answers == correct_answers:

        state.quiz_score += 1

        state.quiz_feedback = (
            "Correct! You know your type matchups!"
        )

    else:

        state.quiz_feedback = (
            "Incorrect! The correct weaknesses are: "
            + ", ".join(correct_answers)
        )

    state.quiz_index += 1

    if state.quiz_index >= 4:
        return quiz_results(state)

    return quiz_weakness(state)

# --------------------------------------------------
# QUIZ RESULTS PAGE
# --------------------------------------------------

@route
def quiz_results(state: State) -> Page:

    score = state.quiz_score

    if score == 4:
        message = "Perfect score! You are a Pokemon Master!"

    elif score >= 3:
        message = "Excellent work, Trainer!"

    elif score >= 2:
        message = "Good effort! Keep practicing!"

    else:
        message = "Keep studying! You can improve!"

    return Page(state, [
        Header("Quiz Results"),

        "You scored " + str(score) + " out of 4.",

        HorizontalRule(),

        Header(message),

        Button("Try Another Quiz", "quiz_menu"),

        Button("Return Home", "index")
    ])


# --------------------------------------------------
# TRAINER NOTE ROUTE
# --------------------------------------------------

@route
def save_note(state: State, trainer_note: str) -> Page:

    state.trainer_note = trainer_note

    return Page(state, [
        Header("Trainer Note Saved!"),

        "Your note has been updated.",

        "Your note: " + state.trainer_note,

        Button("Back Home", "index")
    ])


# --------------------------------------------------
# CLEAR SEARCH HISTORY ROUTE
# --------------------------------------------------

@route
def clear_history(state: State) -> Page:

    state.pokemon_history = []

    state.last_search = ""
    state.last_result = ""

    return Page(state, [
        Header("Search History Cleared!"),

        "Your Pokemon search history has been reset.",

        Button("Return Home", "index")
    ])


# --------------------------------------------------
# START THE WEBSITE
# --------------------------------------------------

start_server(
    State(
        pokemon_history=[],
        last_search="",
        last_result="",
        quiz_kind="",
        quiz_index=0,
        quiz_score=0,
        quiz_feedback="",
        trainer_note="",
        quiz_questions=[]
    )
)

