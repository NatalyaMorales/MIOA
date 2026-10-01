from src.config.settings import DATA_PATH
from src.data.loader import load_response_curves
from src.services.descriptive_agent import simulate_spend


def main():
    response_curve = load_response_curves(DATA_PATH)

    marca = "Lala"
    medio = "OOH"
    proposed_spend = 2_000_000

    result = simulate_spend(
        response_curve=response_curve,
        marca=marca,
        medio=medio,
        proposed_spend=proposed_spend
    )

    # =========================
    # 4. Mostrar resultado
    # =========================

    print("\n==============================")
    print("MEDIA OPTIMIZATION AGENT")
    print("==============================")

    print(f"Marca: {result['marca']}")
    print(f"Medio: {result['medio']}")
    print(f"Modelo: {result['modelo']}")

    print(
        f"Proposed Spend: "
        f"${result['proposed_spend']:,.2f}"
    )

    print(
        f"Expected Response: "
        f"{result['expected_response']:,.2f}"
    )

    print(
        f"ROI: "
        f"{result['roi']:,.4f}"
    )

    print("==============================\n")


if __name__ == "__main__":
    main()