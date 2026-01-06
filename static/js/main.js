/**
 * main.js - The core logic for FinanceFlow
 * Handles Sidebar state, Live Date, Expense Submissions, and Receipts.
 */

// Wait for the DOM to fully load
// This prevents the script from failing to work or execute as expected

document.addEventListener("DOMContentLoaded", () => {
  // Select elements based on the IDs in dashboard.html
  const expenseForm = document.getElementById("expense-form");
  const sidebar = document.getElementById("sidebar");
  const mainWrapper = document.getElementById("main-wrapper");

  // 1. PERSIST SIDEBAR STATE
  // Checks localStorage so the sidebar stays collapsed/expanded after refresh
  const isCollapsed = localStorage.getItem("sidebarCollapsed") === "true";
  if (isCollapsed && sidebar && mainWrapper) {
    sidebar.classList.add("collapsed");
    mainWrapper.classList.add("expanded");
  }

  // Toggle function for the button
  window.toggleSidebar = () => {
    const collapsed = sidebar.classList.toggle("collapsed");
    mainWrapper.classList.toggle("expanded");
    localStorage.setItem("sidebarCollapsed", collapsed);
  };

  // 2. INITIALIZE LIVE DATE
  // Runs the clock immediately on page load
  updateLiveDate();

  // 3. ASYNCHRONOUS EXPENSE ADDITION
  if (expenseForm) {
    expenseForm.addEventListener("submit", async (e) => {
      e.preventDefault();

      // Collect data from the Modal inputs
      const formData = {
        title: document.getElementById("expense-desc").value,
        category: document.getElementById("expense-category").value,
        amount: document.getElementById("expense-amount").value,
      };

      try {
        const response = await fetch("/add_expense", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(formData),
        });

        if (response.ok) {
          // Refresh the page to sync the database and update cards
          window.location.reload();
        } else {
          alert("Failed to save transaction.");
        }
      } catch (error) {
        console.error("Transaction failed:", error);
      }
    });
  }
});

/** * --- GLOBAL FUNCTIONS ---
 * These are defined outside the listener so HTML 'onclick' can trigger them.
 */

// 4. TRANSACTION RECEIPT POPUP
// Formats and displays expense details in a clean alert box
function viewExpenseDetails(title, category, amount, time) {
  const formattedAmount = new Intl.NumberFormat("en-UG").format(amount);
  const detailMsg = `
📊 TRANSACTION RECEIPT
--------------------------
📝 Description: ${title}
🏷️ Category: ${category}
💰 Amount: UGX ${formattedAmount}
⏰ Date/Time: ${time}
--------------------------
Status: ✅ Transaction Verified
    `;
  alert(detailMsg);
}

// 5. LIVE NAVBAR DATE & DAY
// Automatically pulls the current date from the user's system clock
function updateLiveDate() {
  const now = new Date();
  const dayName = now.toLocaleDateString("en-US", { weekday: "long" });
  const dateStr = now.toLocaleDateString("en-US", {
    month: "short",
    day: "2-digit",
    year: "numeric",
  });

  const dayEl = document.getElementById("current-day");
  const dateEl = document.getElementById("current-date");

  if (dayEl && dateEl) {
    dayEl.textContent = dayName;
    dateEl.textContent = dateStr;
  }
}

// 6. BALANCE MODAL ADJUSTMENTS
// Functions to handle the +/- buttons and saving the main wallet balance
function adjustValue(amount) {
  const input = document.getElementById("balance-input");
  let currentValue = parseInt(input.value) || 0;
  input.value = currentValue + amount;
}

function saveNewBalance() {
  const newVal = document.getElementById("balance-input").value;
  const shouldReset = document.getElementById("reset-all-data").checked;

  fetch("/update_balance", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      balance: newVal,
      should_reset: shouldReset,
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.status === "success") {
        window.location.reload();
      }
    })
    .catch((error) => console.error("Error updating balance:", error));
}

function showExpenseDetails(description, category, amount, status, dateTime) {
  // Fill the modal with data
  document.getElementById("modalDescription").innerText = description;
  document.getElementById("modalCategory").innerText = category;
  document.getElementById("modalAmount").innerText = amount;
  document.getElementById("modalDateTime").innerText = dateTime;

  // Show the modal
  var myModal = new bootstrap.Modal(document.getElementById("expenseDetailModal"));
  myModal.show();
}

function handleRowClick(row) {
  // 1. Extract data
  const id = row.getAttribute("data-id"); // Capture the ID
  const title = row.getAttribute("data-title");
  const category = row.getAttribute("data-category");
  const amount = row.getAttribute("data-amount");
  const date = row.getAttribute("data-date");

  // 2. Format amount
  const formattedAmount = "UGX " + Number(amount).toLocaleString();

  // 3. Update Modal Text
  document.getElementById("modalExpenseId").value = id; // Store ID in the hidden input
  document.getElementById("modalDescription").innerText = title;
  document.getElementById("modalCategory").innerText = category;
  document.getElementById("modalAmount").innerText = formattedAmount;
  document.getElementById("modalDateTime").innerText = date;

  // 4. Trigger the Modal (Using the Bootstrap 5 static method)
  const modalElement = document.getElementById("expenseDetailModal");
  const modalInstance = bootstrap.Modal.getOrCreateInstance(modalElement);
  modalInstance.show();
}

async function deleteExpense() {
  const expenseId = document.getElementById("modalExpenseId").value;

  if (confirm("Are you sure you want to delete this expense? This will reimburse your balance.")) {
    try {
      const response = await fetch(`/delete_expense/${expenseId}`, {
        method: "DELETE",
      });

      if (response.ok) {
        window.location.reload(); // Refresh to update card balances
      } else {
        alert("Error deleting expense.");
      }
    } catch (error) {
      console.error("Delete failed:", error);
    }
  }
}
