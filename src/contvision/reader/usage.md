from container_recognition.pipeline import extract_container_id


image_path = "images/container.jpg"

container_id = extract_container_id(image_path)

if container_id:

    print("Container ID:", container_id)

else:

    print("Container ID not detected")