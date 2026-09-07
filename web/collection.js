async function loadCollection() {
    const parameters = new URLSearchParams(window.location.search);
    const collectionId = parameters.get("id");

    const statusMessage = document.querySelector("#status");
    const collectionArticle =
        document.querySelector("#collection");

    if (!collectionId) {
        statusMessage.textContent =
            "No collection was selected.";
        return;
    }

    try {
        const response = await fetch(
            `/collections/${collectionId}`
        );

        if (!response.ok) {
            throw new Error("Collection not found");
        }

        const collection = await response.json();
        document.querySelector("#label-monogram").textContent =
            collection.label
                .split(/\s+/)
                .slice(0, 2)
                .map((word) => word[0])
                .join("")
                .toUpperCase();
        document.querySelector("#collection-label").textContent =
            collection.label;

        document.querySelector("#collection-title").textContent =
            collection.name ||
            `${collection.season} ${collection.release_year}`;

        const credits = document.querySelector("#collection-credits");
        collection.credits.forEach((credit) => {
            const item = document.createElement("li");
            const designerLink = document.createElement("a");
            const role = document.createElement("span");
            designerLink.textContent = credit.designer_name;
            designerLink.href = `/designer.html?id=${credit.designer_id}`;
            role.textContent = credit.role;
            item.append(designerLink, role);
            if (credit.attribution_note) {
                const note = document.createElement("small");
                note.textContent = credit.attribution_note;
                item.append(note);
            }
            credits.append(item);
        });

        document.querySelector("#collection-season").textContent =
            `${collection.label} · ` +
            `${collection.season} ${collection.release_year}`;

        document.querySelector("#collection-status").textContent =
            `Status: ${collection.status}`;

        document.querySelector(
            "#collection-piece-count"
        ).textContent = collection.piece_count === null
            ? "Piece count unavailable"
            : `Piece count: ${collection.piece_count}`;

        document.querySelector(
            "#collection-description"
        ).textContent =
            collection.description ||
            "No description is available.";

        const mediaSection =
            document.querySelector("#collection-media");

        if (collection.youtube_video_id) {
            const videoContainer =
                document.querySelector("#collection-video");
            const iframe = document.createElement("iframe");

            iframe.src =
                `https://www.youtube.com/embed/${collection.youtube_video_id}`;
            iframe.title =
                `${collection.label} ${collection.season} ` +
                `${collection.release_year} runway video`;
            iframe.allow =
                "accelerometer; autoplay; clipboard-write; " +
                "encrypted-media; gyroscope; picture-in-picture; web-share";
            iframe.allowFullscreen = true;
            videoContainer.append(iframe);
            videoContainer.hidden = false;
            mediaSection.hidden = false;
        }

        if (collection.vimeo_video_id) {
            const videoContainer =
                document.querySelector("#collection-vimeo");
            const iframe = document.createElement("iframe");

            iframe.src =
                `https://player.vimeo.com/video/${collection.vimeo_video_id}`;
            iframe.title =
                `${collection.label} ${collection.season} ` +
                `${collection.release_year} Vimeo collection video`;
            iframe.allow = "autoplay; fullscreen; picture-in-picture";
            iframe.allowFullscreen = true;
            videoContainer.append(iframe);
            videoContainer.hidden = false;
            mediaSection.hidden = false;
        }

        if (collection.source_url) {
            const sourceLink = document.createElement("a");

            sourceLink.href = collection.source_url;
            sourceLink.textContent = "View the curated collection source ↗";
            sourceLink.target = "_blank";
            sourceLink.rel = "noopener noreferrer";
            document.querySelector("#collection-source").append(sourceLink);
            mediaSection.hidden = false;
        }

        statusMessage.textContent = "";
        collectionArticle.hidden = false;
    } catch (error) {
        statusMessage.textContent =
            "This collection could not be loaded.";
        console.error(error);
    }
}


loadCollection();
