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

  // Transaction Receipt that pops up when a registered expense is clicked on.
  const editIcon = document.getElementById("enable-edit-desc");
  if (editIcon) {
    editIcon.addEventListener("click", function () {
      const container = document.getElementById("description-edit-container");
      const displaySpan = document.getElementById("modalDescription");
      const currentText = displaySpan.innerText;
      const expenseId = document.getElementById("modalExpenseId").value;

      if (document.getElementById("inline-edit-input")) return;

      container.innerHTML = `
    <div class="input-group input-group-sm w-100">
        <input type="text" class="form-control" id="inline-edit-input" value="${currentText}">
        <button class="btn btn-success" type="button" id="save-inline-btn"><i class="bi bi-check-lg"></i></button>
        <button class="btn btn-light" type="button" id="cancel-inline-btn"><i class="bi bi-x-lg"></i></button>
    </div>
`;

      document.getElementById("save-inline-btn").onclick = async function () {
        const newText = document.getElementById("inline-edit-input").value;
        try {
          const response = await fetch(`/update_expense_description/${expenseId}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title: newText }),
          });
          if (response.ok) window.location.reload();
        } catch (error) {
          console.error("Update failed:", error);
        }
      };

      document.getElementById("cancel-inline-btn").onclick = function () {
        container.innerHTML = "";
        container.appendChild(displaySpan);
      };
    });
  }
});
/** * --- GLOBAL FUNCTIONS ---
 * These are defined outside the listener so HTML 'onclick' can trigger them.
 */

// 4. TRANSACTION RECEIPT POPUP
// Formats and displays expense details in a clean alert box
function viewExpenseDetails(id, title, category, amount, time, isCovered) {
  // 1. Format the money
  const formattedAmount = new Intl.NumberFormat("en-UG").format(amount);

  // 2. Inject data into your Modal elements
  document.getElementById("modalExpenseId").value = id;
  document.getElementById("modalDescription").innerText = title;
  document.getElementById("modalCategory").innerText = category;
  document.getElementById("modalAmount").innerText = `UGX ${formattedAmount}`;
  document.getElementById("modalDateTime").innerText = time;

  // 3. Handle Button Visibility (Hide "Mark as Paid" if already covered)
  const markPaidBtn = document.getElementById("markPaidBtn");
  if (isCovered === "True" || isCovered === true) {
    markPaidBtn.classList.add("d-none");
  } else {
    markPaidBtn.classList.remove("d-none");
  }

  // 4. Show the Soft-Edged Modal
  const myModal = new bootstrap.Modal(document.getElementById("expenseDetailModal"));
  myModal.show();
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
  const date = row.getAttribute("data-date"); // This now gets "06 Jan, 2026 | 01:06 PM"

  // 2. Format amount
  const formattedAmount = "UGX " + Number(amount).toLocaleString();

  // 3. Update Modal Text
  document.getElementById("modalExpenseId").value = id; // Store ID in the hidden input
  document.getElementById("modalDescription").innerText = title;
  document.getElementById("modalCategory").innerText = category;
  document.getElementById("modalAmount").innerText = formattedAmount;
  document.getElementById("modalDateTime").innerText = date;

  // 3.5 Status Logic: Show/Hide "Mark as Paid" button
  // This checks the expense's status and adjusts button visibility accordingly
  const isCovered = row.getAttribute("data-covered") === "True";
  const markPaidBtn = document.getElementById("markPaidBtn");

  if (isCovered) {
    markPaidBtn.classList.add("d-none"); // Hide if already paid
  } else {
    markPaidBtn.classList.remove("d-none"); // Show if pending
  }

  // 4. Trigger the Modal (Using the Bootstrap 5 static method)
  const modalElement = document.getElementById("expenseDetailModal");
  const modalInstance = bootstrap.Modal.getOrCreateInstance(modalElement);
  modalInstance.show();
}

// NEW: Logic to switch between Receipt and Confirmation views
function toggleDeleteConfirm(isConfirming) {
  const receiptView = document.getElementById("receipt-view");
  const confirmView = document.getElementById("confirm-view");
  const receiptFooter = document.getElementById("receipt-footer-btns");
  const confirmFooter = document.getElementById("confirm-footer-btns");

  if (isConfirming) {
    // Hide receipt, show confirmation
    receiptView.classList.add("d-none");
    receiptFooter.classList.add("d-none");
    confirmView.classList.remove("d-none");
    confirmFooter.classList.remove("d-none");
  } else {
    // Hide confirmation, show receipt
    receiptView.classList.remove("d-none");
    receiptFooter.classList.remove("d-none");
    confirmView.classList.add("d-none");
    confirmFooter.classList.add("d-none");
  }
}

// NEW: The actual deletion logic that communicates with Flask
async function executeDelete() {
  const expenseId = document.getElementById("modalExpenseId").value;

  try {
    const response = await fetch(`/delete_expense/${expenseId}`, {
      method: "DELETE", // Ensure this matches your route in app.py
    });

    if (response.ok) {
      window.location.reload(); // Success! Refresh to update UI and totals
    } else {
      const errorData = await response.json();
      alert("Error: " + (errorData.message || "Failed to delete expense."));
    }
  } catch (error) {
    console.error("Delete failed:", error);
    alert("Network error. Could not connect to the server.");
  }
}

// IMPORTANT: Add this to reset the modal view whenever it's closed
// This ensures that next time you open a receipt, it doesn't stay on the "Are you sure" screen
document.getElementById("expenseDetailModal").addEventListener("hidden.bs.modal", function () {
  toggleDeleteConfirm(false);

  // CLEANUP: If the user was editing and closed the modal, put the text back
  const container = document.getElementById("description-edit-container");
  const displaySpan = document.getElementById("modalDescription");
  if (container && displaySpan && document.getElementById("inline-edit-input")) {
    container.innerHTML = "";
    container.appendChild(displaySpan);
  }
});

// 7. BALANCE RESET CONFIRMATION LOGIC
// Switches between the Input form and the Warning card in the Balance Modal
// Function called by 2 buttons: the Toggle/Slide button in the Total Balance card and the new Delete
// All button attached to the dashboard at the end of the List

function toggleResetConfirm(showWarning) {
  const setupView = document.getElementById("balance-setup-view");
  const confirmView = document.getElementById("reset-confirm-view");

  if (showWarning) {
    setupView.classList.add("d-none");
    confirmView.classList.remove("d-none");
  } else {
    setupView.classList.remove("d-none");
    confirmView.classList.add("d-none");
  }
}

// Logic for the "Update Balance" button inside the modal
function checkResetFlag() {
  const shouldReset = document.getElementById("reset-all-data").checked;

  if (shouldReset) {
    toggleResetConfirm(true); // Intercept and show the warning card
  } else {
    saveNewBalance(); // Proceed immediately if toggle is OFF
  }
}

// Ensure the balance modal resets its view when closed
document.getElementById("updateBalanceModal").addEventListener("hidden.bs.modal", function () {
  toggleResetConfirm(false);
  document.getElementById("reset-all-data").checked = false;
});

// 8. MARK AS PAID FUNCTIONALITY
// Sends a request to mark the expense as paid and updates the UI accordingly
function markAsPaid() {
  const expenseId = document.getElementById("modalExpenseId").value;
  const markPaidBtn = document.getElementById("markPaidBtn");

  // Add a loading state to the button
  markPaidBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Updating...';
  markPaidBtn.disabled = true;

  fetch(`/mark_as_paid/${expenseId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.status === "success") {
        // Success! Refresh the page to update balances and table status
        window.location.reload();
      } else {
        alert("Error: " + (data.message || "Could not update status."));
        // Reset button if it fails
        markPaidBtn.innerHTML = '<i class="bi bi-check-lg me-2"></i>Mark as Paid';
        markPaidBtn.disabled = false;
      }
    })
    .catch((error) => {
      console.error("Error:", error);
      alert("An error occurred. Please check your connection.");
      markPaidBtn.disabled = false;
    });
}

// 9. ASYNCHRONOUS EXPENSE SUBMISSION
// Handles the submission of new expenses via the modal form when a user clicks "Add Expense"
document.getElementById("expense-form").addEventListener("submit", async function (e) {
  e.preventDefault();

  // Capture values from your new premium IDs
  const description = document.getElementById("expense-description").value;
  const category = document.getElementById("expense-category").value;
  const amount = document.getElementById("expense-amount").value;

  const expenseData = {
    title: description,
    category: category,
    amount: parseFloat(amount),
    date_to_handle: new Date().toISOString(), // Capturing current time for the task
  };

  try {
    const response = await fetch("/add_expense", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(expenseData),
    });

    if (response.ok) {
      // Success: Reload to show the new expense in the "Registered Expenses" table
      window.location.reload();
    } else {
      alert("Error saving the expenditure task.");
    }
  } catch (error) {
    console.error("Fetch error:", error);
  }
});
