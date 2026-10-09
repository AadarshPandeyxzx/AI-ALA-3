
const form = document.getElementById("chat-form");
const input = document.getElementById("user-input");
const messages = document.getElementById("messages");
const sendButton = document.getElementById("send-btn");

const quickButtons = document.querySelectorAll(".quick-btn");

// Add a message to the chat window
function addMessage(text, sender) {
    const row = document.createElement("div");
    row.className = `message-row ${sender}-row`;

    const bubble = document.createElement("div");
    bubble.className = `message ${sender}-message`;

    // Display text safely
    bubble.textContent = text;

    row.appendChild(bubble);
    messages.appendChild(row);

    // Scroll to the latest message
    messages.scrollTop = messages.scrollHeight;
}

// Send a message to the Flask chatbot
async function sendMessage(message) {
    const cleanMessage = message.trim();

    if (!cleanMessage) {
        return;
    }

    // Display the user's message
    addMessage(cleanMessage, "user");

    input.value = "";
    sendButton.disabled = true;

    try {
        const response = await fetch("/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                message: cleanMessage
            })
        });

        const data = await response.json();

        if (!response.ok) {
            addMessage(
                data.response ||
                "Sorry, I couldn't process your request.",
                "bot"
            );
        } else {
            addMessage(
                data.response ||
                "Sorry, I couldn't find an answer.",
                "bot"
            );
        }
    } catch (error) {
        addMessage(
            "I couldn't connect to the chatbot server. " +
            "Please make sure app.py is running and try again.",
            "bot"
        );

        console.error("Chatbot error:", error);
    } finally {
        sendButton.disabled = false;
        input.focus();
    }
}

// Handle the message form
form.addEventListener("submit", function (event) {
    event.preventDefault();
    sendMessage(input.value);
});

// Handle quick-question buttons
quickButtons.forEach(function (button) {
    button.addEventListener("click", function () {
        const question = button.dataset.question || "";
        sendMessage(question);
    });
});

// Focus on the input when the page loads
input.focus();