import argparse
import sys


def main() -> None:
	parser = argparse.ArgumentParser(
		description="Convierte temperaturas entre Celsius y Fahrenheit."
	)
	parser.add_argument("valor", type=float, help="Temperatura a convertir")
	parser.add_argument(
		"-t",
		"--to",
		required=True,
		choices=["celsius", "fahrenheit"],
		help="Unidad de destino",
	)

	try:
		args = parser.parse_args()
	except SystemExit as e:
		if e.code == 0:
			raise
		sys.exit(1)

	if args.to == "fahrenheit":
		convertido = (args.valor * 9 / 5) + 32
		print(f"{args.valor:g}°C = {convertido:.1f}°F")
	else:
		convertido = (args.valor - 32) * 5 / 9
		if abs(convertido - round(convertido, 1)) < 1e-9:
			print(f"{args.valor:g}°F = {convertido:.1f}°C")
		else:
			print(f"{args.valor:g}°F = {convertido:.2f}°C")


if __name__ == "__main__":
	main()
