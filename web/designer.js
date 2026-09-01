async function loadDesigner() {
    const parameters = new URLSearchParams(window.location.search);
    const designerId = parameters.get("id");

    const status = document.querySelector("#status");
    const profile = document.querySelector("#profile");

    if (!designerId) {
        status.textContent = "No designer was selected.";
        return;
    }

    try {
        const designerResponse = await fetch(
            `/designers/${designerId}`
        );

        if (!designerResponse.ok) {
            throw new Error("Designer not found");
        }

        const collectionsResponse = await fetch(
            `/designers/${designerId}/collections`
        );

        if (!collectionsResponse.ok) {
            throw new Error("Collections could not be loaded");
        }

        const designer = await designerResponse.json();
        const collections = await collectionsResponse.json();
        document.querySelector("#profile-id").textContent =
            `DESIGNER PROFILE / ID ${String(designer.id).padStart(3, "0")}`;
        document.querySelector("#collection-count").textContent =
            `${String(collections.length).padStart(2, "0")} RECORDS`;
        const flags = nationalityFlags(designer.nationality);
        const flagElement = document.querySelector("#designer-flag");
        flagElement.textContent = flags;
        flagElement.hidden = !flags;
        document.querySelector("#designer-name-text").textContent =
            designer.full_name;

        const details = [
            designer.nationality,
            designer.birth_year
                ? `Born ${designer.birth_year}`
                : null,
        ].filter(Boolean);

        const websiteContainer =
            document.querySelector("#designer-website");

        if (designer.website) {
            const websiteLink = document.createElement("a");

            websiteLink.href = designer.website;
            websiteLink.textContent = "Official transmission ↗";
            websiteLink.target = "_blank";
            websiteLink.rel = "noopener noreferrer";

            websiteContainer.append(websiteLink);
        } else {
            websiteContainer.textContent =
                "No website is available.";
        }

        document.querySelector("#designer-details").textContent =
            details.join(" · ");

        document.querySelector("#designer-biography").textContent =
            designer.biography || "No biography is available.";

        const collectionList =
            document.querySelector("#collection-list");

        for (const [index, collection] of collections.entries()) {
            const item = document.createElement("li");
            const link = document.createElement("a");
            const number = document.createElement("i");
            const title = document.createElement("strong");
            const season = document.createElement("span");

            number.textContent = String(index + 1).padStart(2, "0");
            title.textContent = collection.name || collection.label;
            season.textContent = collection.name
                ? `${collection.label} · ${collection.season} ${collection.release_year}`
                : `${collection.season} ${collection.release_year}`;
            link.href = `/collection.html?id=${collection.id}`;
            link.append(number, title, season);
            item.append(link);
            collectionList.append(item);
        }

        status.textContent = "";
        profile.hidden = false;

    } catch (error) {
        status.textContent =
            "This designer profile could not be loaded.";
        console.error(error);
    }
}


loadDesigner();
