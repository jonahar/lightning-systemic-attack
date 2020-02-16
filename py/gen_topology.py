import json

num_victims = 10
sender = 1
receiver = 3
first_victim = 4

victim_ids = [str(i) for i in range(first_victim, first_victim + num_victims)]

d = {
    str(sender): {"peers": victim_ids, "client": "c-lightning"},
    str(receiver): {"peers": [], "evil": True, "client": "c-lightning"},
}

for id in victim_ids:
    d[id] = {"peers": [str(receiver)], "client": "lnd"}

print(json.dumps(d, indent=4))
