const parameters = new URLSearchParams(window.location.search);
let designerId = parameters.get("designer_id");
const collectionId = parameters.get("collection_id");
const isEditing = Boolean(collectionId);

const form = document.querySelector("#collection-form");
const statusMessage = document.querySelector("#status");


if (!designerId && !isEditing) {
    statusMessage.textContent = "No designer was selected.";
    form.hidden = true;
}

async function loadCollectionForEditing() {
    if (!isEditing) {
        return;
    }

    statusMessage.textContent = "Loading collection...";

    try {
        const response = await fetch(
            `/collections/${collectionId}`
        );

        if (!response.ok) {
            throw new Error("Collection could not be loaded");
        }

        const collection = await response.json();

        designerId = collection.designer_id;

        document.querySelector("#form-title").textContent =
            "Edit Collection";

        document.querySelector("#submit-button").textContent =
            "Save changes";

        document.querySelector("#label").value =
            collection.label;

        document.querySelector("#name").value =
            collection.name || "";

        document.querySelector("#season").value =
            collection.season;

        document.querySelector("#release-year").value =
            collection.release_year;

        document.querySelector("#collection-status").value =
            collection.status;

        document.querySelector("#piece-count").value =
            collection.piece_count ?? "";

        document.querySelector("#description").value =
            collection.description || "";

        document.querySelector("#source-url").value =
            collection.source_url || "";

        document.querySelector("#youtube-video").value =
            collection.youtube_video_id || "";
        document.querySelector("#vimeo-video").value =
            collection.vimeo_video_id || "";

        statusMessage.textContent = "";
    } catch (error) {
        statusMessage.textContent = error.message;
        form.hidden = true;
    }
}


loadCollectionForEditing();

form.addEventListener("submit", async function (event) {
    event.preventDefault();

    const formData = new FormData(form);
    const pieceCount = formData.get("piece_count");

    const payload = {
        designer_id: Number(designerId),
        label: formData.get("label"),
        name: formData.get("name") || null,
        season: formData.get("season"),
        release_year: Number(formData.get("release_year")),
        status: formData.get("status"),
        piece_count: pieceCount ? Number(pieceCount) : null,
        description: formData.get("description") || null,
        source_url: formData.get("source_url") || null,
        youtube_video_id:
            formData.get("youtube_video_id") || null,
        vimeo_video_id:
            formData.get("vimeo_video_id") || null,
    };

    statusMessage.textContent = "Saving collection...";
    statusMessage.classList.remove("error");

    try {
        const endpoint = isEditing
            ? `/collections/${collectionId}`
            : "/collections";

        const method = isEditing
            ? "PUT"
            : "POST";
        const response = await fetch(endpoint, {
            method: method,
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        });

        const result = await readJson(
            response,
            "Collection could not be saved"
        );

        window.location.href =
            `/collection.html?id=${result.id}`;
    } catch (error) {
        statusMessage.textContent = error.message;
        statusMessage.classList.toggle("error", true);
        statusMessage.scrollIntoView({
            behavior: "smooth",
            block: "center",
        });
    }
});
