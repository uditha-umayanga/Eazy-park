self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SHOW_EXIT_BILL") {
    const { plate, duration, bill } = event.data;
    self.registration.showNotification("Thank you for using our service! 🚘", {
      body: `Vehicle: ${plate}\nDuration: ${duration}s | Total Bill: LKR ${bill}`,
      icon: "https://cdn-icons-png.flaticon.com/512/3202/3202926.png",
      vibrate: [200, 100, 200],
      requireInteraction: true
    });
  }
});