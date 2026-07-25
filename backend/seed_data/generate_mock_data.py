import random

REGIONS = [
    "PJM",
    "MISO",
    "SPP",
    "ERCOT"
]

def generate_substations():

    substations = []

    for region in REGIONS:
        for i in range(50):

            substations.append({
                "substation_name": f"{region}_SUB_{i}",
                "region": region,
                "withdrawal_rate":
                    round(random.uniform(0.65, 0.90), 2)
            })

    return substations


if __name__ == "__main__":

    substations = generate_substations()

    print(
        f"Generated {len(substations)} substations"
    )
