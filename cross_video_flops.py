from difflib import SequenceMatcher
import json

flop_test_data = {
    "flops": [
        {
            "players": [
                {
                    "player_name": "Marc Cucurella",
                    "player_team_name": "CHE",
                    "injured": False,
                    "flop_start_video_time": 400.0,
                    "flop_end_video_time": 402.26,
                    "flop_start_game_time": "27:10",
                    "flop_end_game_time": "27:12",
                }
            ],
            "referee_decisions": [],
        },
        {
            "players": [
                {
                    "player_name": "Marc Cucurella",
                    "player_team_name": "Chelsea",
                    "injured": False,
                    "flop_start_video_time": 392.0,
                    "flop_end_video_time": 399.0,
                    "flop_start_game_time": "27:01",
                    "flop_end_game_time": "27:06",
                }
            ],
            "referee_decisions": [],
        },
    ]
}


def extract_surname(full_name):
    """Extracts the surname from a player's full name."""
    return full_name.split()[-1] if full_name else ""


def similar(a, b):
    """Returns similarity ratio between two strings."""
    return SequenceMatcher(None, a, b).ratio()


def handle_cross_video_flops(flop_data, time_threshold=3, similarity_threshold=0.7):
    """Merges flops that span across two video segments if they are close in time and involve at least one similar surname."""

    # Step 1: Sort flops by start video time
    flop_data.sort(
        key=lambda flop: min(p["flop_start_video_time"] for p in flop["players"])
    )

    # print("\nSorted flops based on start time:")
    # for flop in flop_data:
    #     print(json.dumps(flop, indent=4))

    merged_flops = []
    prev_flop = None

    for index, flop_event in enumerate(flop_data):
        # print(f"\nProcessing flop {index}:")
        # print(json.dumps(flop_event, indent=4))

        if not prev_flop:
            prev_flop = flop_event
            continue

        prev_surnames = {
            extract_surname(p["player_name"])
            for p in prev_flop["players"]
            if p["player_name"]
        }
        current_surnames = {
            extract_surname(p["player_name"])
            for p in flop_event["players"]
            if p["player_name"]
        }

        common_players = any(
            similar(prev, curr) >= similarity_threshold
            for prev in prev_surnames
            for curr in current_surnames
        )

        prev_end_time = max(p["flop_end_video_time"] for p in prev_flop["players"])
        current_start_time = min(
            p["flop_start_video_time"] for p in flop_event["players"]
        )

        # print(f"\nChecking merge conditions between previous flop and current flop:")
        # print(f"  Previous flop end time: {prev_end_time}")
        # print(f"  Current flop start time: {current_start_time}")
        # print(
        #     f"  Time difference: {abs(current_start_time - prev_end_time)} (Threshold: {time_threshold})"
        # )
        # print(f"  Previous surnames: {prev_surnames}")
        # print(f"  Current surnames: {current_surnames}")
        # print(f"  Common player match found: {common_players}")

        if common_players and abs(current_start_time - prev_end_time) <= time_threshold:
            print("\n  ******************")
            print("  Merging two flops!")
            print("  ******************\n")

            # Merge players while ensuring earliest start time and latest end time for each
            player_map = {}
            for player in prev_flop["players"] + flop_event["players"]:
                name = player["player_name"]
                if name in player_map:
                    # Update timestamps
                    player_map[name]["flop_start_video_time"] = min(
                        player_map[name]["flop_start_video_time"],
                        player["flop_start_video_time"],
                    )
                    player_map[name]["flop_end_video_time"] = max(
                        player_map[name]["flop_end_video_time"],
                        player["flop_end_video_time"],
                    )
                    player_map[name]["flop_start_game_time"] = min(
                        player_map[name]["flop_start_game_time"],
                        player["flop_start_game_time"],
                    )
                    player_map[name]["flop_end_game_time"] = max(
                        player_map[name]["flop_end_game_time"],
                        player["flop_end_game_time"],
                    )
                else:
                    # Add new player entry
                    player_map[name] = player

            prev_flop["players"] = list(player_map.values())

            # Deduplicate referee decisions
            prev_flop["referee_decisions"] = list(
                set(prev_flop["referee_decisions"] + flop_event["referee_decisions"])
            )

        else:
            print("\nFlops not merged. Adding previous flop to merged list.")
            merged_flops.append(prev_flop)
            prev_flop = flop_event

    if prev_flop:
        merged_flops.append(prev_flop)

    return merged_flops


# merged_flops = handle_cross_video_flops(flop_test_data["flops"])
# print(json.dumps(merged_flops, indent=4))
