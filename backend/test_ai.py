from app.services.ai_analyzer import analyze_incident


incident = {
    "source_ip": "99.86.159.111",
    "destination_ip": "172.27.153.250",
    "source_port": 80,
    "destination_port": 58216,
    "protocol": "TCP",
    "event_type": "GPL ATTACK_RESPONSE id check returned root",
    "severity": "HIGH",
    "description": (
        "Potentially Bad Traffic - "
        "GPL ATTACK_RESPONSE id check returned root"
    )
}


result = analyze_incident(incident)

print()
print("=" * 70)
print("SENTINEL AI ANALYSIS")
print("=" * 70)
print(result)
print("=" * 70)