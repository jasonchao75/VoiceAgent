import "./login.css";

const form = document.querySelector("#login-form");
const notice = document.querySelector("#login-notice");
const password = document.querySelector("#password");
const showPassword = document.querySelector("#show-password");
const submit = form.querySelector('button[type="submit"]');
const params = new URLSearchParams(window.location.search);

function showNotice(message, kind = "error") {
  notice.textContent = message;
  notice.dataset.kind = kind;
  notice.hidden = false;
}

if (params.has("expired")) {
  showNotice("Your session expired after a period of inactivity. Sign in to continue where you left off.", "info");
}

showPassword.addEventListener("click", () => {
  const reveal = password.type === "password";
  password.type = reveal ? "text" : "password";
  showPassword.textContent = reveal ? "Hide" : "Show";
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  submit.disabled = true;
  submit.textContent = "Signing in…";
  notice.hidden = true;
  try {
    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({
        username: form.elements.username.value,
        password: form.elements.password.value,
        next: params.get("next") || "/",
      }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || "Sign in failed. Please try again.");
    window.location.assign(payload.next || "/");
  } catch (error) {
    showNotice(error instanceof Error ? error.message : "Sign in failed. Please try again.");
    password.select();
  } finally {
    submit.disabled = false;
    submit.textContent = "Continue to VoiceAgent Demo";
  }
});
