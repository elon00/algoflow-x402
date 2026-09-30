// AlgoFlow x402 Web Client

let currentNetwork = "mainnet";

document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  initNetworkStatus();
  loadBounties();
  initInspector();
  initWalletTools();
  initTokenTools();
  initModal();
});

// Tab Switcher
function initTabs() {
  const tabs = document.querySelectorAll(".tab-btn");
  tabs.forEach(btn => {
    btn.addEventListener("click", () => {
      tabs.forEach(t => t.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));

      btn.classList.add("active");
      const targetId = btn.getAttribute("data-tab");
      document.getElementById(targetId).classList.add("active");
    });
  });
}

// Network Status
async function initNetworkStatus() {
  const badge = document.getElementById("networkBadge");
  const netName = document.getElementById("networkName");
  const roundEl = document.getElementById("roundNumber");
  const statRound = document.getElementById("statRound");
  const statLatency = document.getElementById("statLatency");
  const switchBtn = document.getElementById("switchNetworkBtn");

  async function poll() {
    const start = performance.now();
    try {
      const res = await fetch("/api/network");
      const data = await res.json();
      const latency = Math.round(performance.now() - start);

      currentNetwork = data.network;
      netName.textContent = data.network.toUpperCase();
      roundEl.textContent = `Round: #${data.round?.toLocaleString() || "Syncing"}`;
      statRound.textContent = data.round ? `#${data.round.toLocaleString()}` : "Active";
      statLatency.textContent = `Latency: ${latency}ms • Node: AlgoNode`;

      if (data.is_mainnet) {
        badge.style.borderColor = "rgba(0, 255, 136, 0.4)";
      } else {
        badge.style.borderColor = "rgba(255, 183, 3, 0.4)";
      }
    } catch (err) {
      statLatency.textContent = "Node unreachable";
    }
  }

  await poll();
  setInterval(poll, 15000);

  switchBtn.addEventListener("click", async () => {
    const target = currentNetwork === "mainnet" ? "testnet" : "mainnet";
    switchBtn.disabled = true;
    switchBtn.textContent = "Switching...";
    try {
      await fetch("/api/network/switch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ network: target }),
      });
      await poll();
    } catch (e) {
      alert("Error switching network: " + e);
    } finally {
      switchBtn.disabled = false;
      switchBtn.textContent = `Switch Network`;
    }
  });
}

// Bounties Management
async function loadBounties() {
  const container = document.getElementById("bountiesList");
  try {
    const res = await fetch("/api/bounties");
    const bounties = await res.json();

    if (!bounties || bounties.length === 0) {
      container.innerHTML = '<div style="padding:40px; text-align:center; color:var(--text-muted);">No active bounties found. Create one to get started!</div>';
      return;
    }

    // Update total locked
    const totalAlgo = bounties.reduce((acc, b) => acc + (b.amount_algo || 0), 0);
    document.getElementById("statEscrow").textContent = `${totalAlgo.toFixed(1)} ALGO`;

    container.innerHTML = bounties.map(b => renderBountyCard(b)).join("");
  } catch (err) {
    container.innerHTML = `<div style="padding:40px; text-align:center; color:var(--accent-rose);">Failed to load bounties: ${err.message}</div>`;
  }
}

function renderBountyCard(b) {
  let badgeClass = "badge-open";
  if (b.status === "CLAIMED") badgeClass = "badge-claimed";
  if (b.status === "RESOLVED") badgeClass = "badge-resolved";
  if (b.status === "CLOSED") badgeClass = "badge-closed";

  const shortEscrow = b.escrow_address ? `${b.escrow_address.slice(0, 8)}...${b.escrow_address.slice(-6)}` : "Pending";
  const shortTech = b.technician ? `${b.technician.slice(0, 8)}...${b.technician.slice(-6)}` : "Unassigned";

  let actionButtons = "";
  if (b.status === "OPEN") {
    actionButtons = `<button class="btn btn-outline btn-sm" onclick="claimBounty('${b.id}')">⚡ Claim Bounty</button>`;
  } else if (b.status === "CLAIMED") {
    actionButtons = `<button class="btn btn-primary btn-sm" onclick="resolveBounty('${b.id}')">✓ Submit Resolution & Evidence</button>`;
  } else if (b.status === "RESOLVED") {
    actionButtons = `<button class="btn btn-primary btn-sm" onclick="releaseBounty('${b.id}')">💰 Release Payment (Atomic ITXN)</button>`;
  } else if (b.status === "CLOSED") {
    actionButtons = `<span style="font-size:12px; color:var(--accent-green); font-family:var(--font-mono);">✓ Settled On-Chain (${b.settlement_txid ? b.settlement_txid.slice(0, 14) + '...' : 'Confirmed'})</span>`;
  }

  return `
    <div class="bounty-card">
      <div class="bounty-top">
        <div>
          <span class="badge ${badgeClass}">${b.status}</span>
          <span style="font-size:11px; margin-left:8px; color:var(--text-muted); font-family:var(--font-mono);">${b.category} • ${b.priority}</span>
          <h3 class="bounty-title" style="margin-top:6px;">${escapeHtml(b.title)}</h3>
        </div>
        <div style="text-align:right;">
          <div style="font-size:20px; font-weight:800; color:var(--accent-cyan); font-family:var(--font-mono);">${b.amount_algo} ALGO</div>
          <div style="font-size:11px; color:var(--text-muted); font-family:var(--font-mono);">${b.amount_microalgos?.toLocaleString()} µALGO</div>
        </div>
      </div>

      <div class="bounty-desc">${escapeHtml(b.description)}</div>

      ${b.evidence_notes ? `
        <div style="background:rgba(157, 78, 221, 0.1); border-left:3px solid var(--accent-purple); padding:8px 12px; margin-bottom:12px; font-size:12px; border-radius:0 6px 6px 0;">
          <strong>Evidence Note:</strong> ${escapeHtml(b.evidence_notes)}<br>
          <span style="font-family:var(--font-mono); color:var(--accent-purple); font-size:11px;">SHA-256: ${b.evidence_hash}</span>
        </div>
      ` : ""}

      <div class="bounty-meta-row">
        <div>📍 Location: <span style="color:#fff;">${escapeHtml(b.location || "N/A")}</span></div>
        <div>🏛️ App ID: <span style="color:var(--accent-cyan);">${b.app_id || "N/A"}</span></div>
        <div>🔒 Escrow Address: <span style="color:#fff;">${shortEscrow}</span></div>
        <div>🔧 Technician: <span style="color:#fff;">${shortTech}</span></div>
      </div>

      <div class="bounty-actions">
        ${actionButtons}
      </div>
    </div>
  `;
}

// Bounty Actions
window.claimBounty = async function(id) {
  const techAddress = prompt("Enter your Algorand Technician Address (or leave blank to use demo address):", "PKPE4HCDPQS56QPG5FNUWECRWSZDJRFQ7OXF6CYJNFYVVUCMAMMX3X2D2M");
  if (!techAddress) return;

  try {
    const res = await fetch(`/api/bounties/${id}/claim`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ technician_address: techAddress.trim() }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to claim bounty");
    alert("Bounty claimed successfully! State advanced to CLAIMED.");
    loadBounties();
  } catch (e) {
    alert("Claim error: " + e.message);
  }
};

window.resolveBounty = async function(id) {
  const notes = prompt("Enter resolution notes / completion evidence details:", "Inspected component, replaced worn seals, verified zero leakage under pressure.");
  if (!notes) return;

  try {
    const res = await fetch(`/api/bounties/${id}/resolve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        technician_address: "W34V7RZY6R7QJNZF5Q4Z3A3M7M3Q7Z7Q3Z7Q3Z7Q3Z7Q3Z7Q3Z7Q3Z7Q3Z",
        resolution_notes: notes,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to resolve bounty");
    alert(`Resolution committed with SHA-256 evidence hash:\n${data.evidence_hash}`);
    loadBounties();
  } catch (e) {
    alert("Resolution error: " + e.message);
  }
};

window.releaseBounty = async function(id) {
  if (!confirm("Release escrow payment to technician? This triggers an atomic Algorand Inner Transaction (ITXN).")) return;

  try {
    const res = await fetch(`/api/bounties/${id}/release`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to release payout");
    alert(`Payment atomic settlement confirmed!\nTXID: ${data.settlement.txid}\nRecipient: ${data.settlement.recipient}`);
    loadBounties();
  } catch (e) {
    alert("Release error: " + e.message);
  }
};

// x402 Protocol Inspector
function initInspector() {
  const endpointSelect = document.getElementById("x402Endpoint");
  const paramInput = document.getElementById("x402Param");
  const sendUnpaidBtn = document.getElementById("sendUnpaidBtn");
  const sendPaidBtn = document.getElementById("sendPaidBtn");
  const customTxid = document.getElementById("customTxid");
  const statusTag = document.getElementById("responseStatusTag");
  const headersBox = document.getElementById("responseHeadersBox");
  const bodyBox = document.getElementById("responseBodyBox");

  let lastChallenge = null;

  sendUnpaidBtn.addEventListener("click", async () => {
    const url = `${endpointSelect.value}?asset_id=${encodeURIComponent(paramInput.value)}`;
    headersBox.textContent = "Sending GET " + url + " ...";
    bodyBox.textContent = "";

    try {
      const res = await fetch(url);
      const data = await res.json();

      statusTag.style.display = "inline-block";
      statusTag.textContent = `${res.status} Payment Required`;
      statusTag.className = "status-tag tag-402";

      // Display response headers
      const headersObj = {};
      res.headers.forEach((val, key) => {
        if (key.toLowerCase().startsWith("x-402") || key.toLowerCase() === "www-authenticate") {
          headersObj[key] = val;
        }
      });
      headersBox.textContent = JSON.stringify(headersObj, null, 2);
      bodyBox.textContent = JSON.stringify(data, null, 2);

      if (data.payment) {
        lastChallenge = data.payment.challenge;
        customTxid.placeholder = `Demo TXID will verify challenge: ${data.payment.challenge}`;
      }
    } catch (e) {
      bodyBox.textContent = "Error: " + e.message;
    }
  });

  sendPaidBtn.addEventListener("click", async () => {
    const url = `${endpointSelect.value}?asset_id=${encodeURIComponent(paramInput.value)}`;
    let txid = customTxid.value.trim();
    if (!txid) {
      txid = "mock_" + Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
      customTxid.value = txid;
    }

    headersBox.textContent = `Sending GET ${url}\nHeader: X-402-Payment-Authorization: txid=${txid}`;
    bodyBox.textContent = "";

    try {
      const res = await fetch(url, {
        headers: {
          "X-402-Payment-Authorization": `txid=${txid}`,
        }
      });
      const data = await res.json();

      statusTag.style.display = "inline-block";
      if (res.status === 200) {
        statusTag.textContent = `200 OK (Payment Verified)`;
        statusTag.className = "status-tag tag-200";
      } else {
        statusTag.textContent = `${res.status} ${res.statusText}`;
        statusTag.className = "status-tag tag-402";
      }

      const headersObj = {};
      res.headers.forEach((val, key) => {
        if (key.toLowerCase().startsWith("x-402")) {
          headersObj[key] = val;
        }
      });
      headersBox.textContent = JSON.stringify(headersObj, null, 2);
      bodyBox.textContent = JSON.stringify(data, null, 2);
    } catch (e) {
      bodyBox.textContent = "Error: " + e.message;
    }
  });
}

// Wallet Tools
function initWalletTools() {
  const genBtn = document.getElementById("generateKeyBtn");
  const genAddress = document.getElementById("genAddress");
  const genMnemonic = document.getElementById("genMnemonic");
  const checkBtn = document.getElementById("checkBalanceBtn");
  const checkInput = document.getElementById("checkAddressInput");
  const balanceBox = document.getElementById("balanceResultBox");

  genBtn.addEventListener("click", async () => {
    genBtn.disabled = true;
    genBtn.textContent = "Generating...";
    try {
      const res = await fetch("/api/network/wallet/generate");
      const data = await res.json();
      genAddress.value = data.address;
      genMnemonic.value = data.mnemonic;
      checkInput.value = data.address;
    } catch (e) {
      alert("Error generating account: " + e);
    } finally {
      genBtn.disabled = false;
      genBtn.textContent = "Generate New Algorand Account";
    }
  });

  checkBtn.addEventListener("click", async () => {
    const addr = checkInput.value.trim();
    if (!addr) {
      alert("Please enter an Algorand address.");
      return;
    }
    balanceBox.textContent = "Querying live node...";
    try {
      const res = await fetch(`/api/network/wallet/balance/${addr}`);
      const data = await res.json();
      balanceBox.textContent = JSON.stringify(data, null, 2);
    } catch (e) {
      balanceBox.textContent = "Error: " + e.message;
    }
  });
}

// Modal for Creating Bounty
function initModal() {
  const modal = document.getElementById("createModal");
  const openBtn = document.getElementById("openCreateModalBtn");
  const closeBtn = document.getElementById("closeCreateModalBtn");
  const cancelBtn = document.getElementById("cancelCreateModalBtn");
  const form = document.getElementById("createBountyForm");

  const openModal = () => modal.classList.add("active");
  const closeModal = () => modal.classList.remove("active");

  openBtn.addEventListener("click", openModal);
  closeBtn.addEventListener("click", closeModal);
  cancelBtn.addEventListener("click", closeModal);

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const title = document.getElementById("formTitle").value.trim();
    const desc = document.getElementById("formDesc").value.trim();
    const category = document.getElementById("formCategory").value;
    const priority = document.getElementById("formPriority").value;
    const location = document.getElementById("formLocation").value.trim();
    const amount = parseFloat(document.getElementById("formAmount").value);

    try {
      const res = await fetch("/api/bounties", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title,
          description: desc,
          category,
          priority,
          location,
          amount_algo: amount,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to create bounty");
      closeModal();
      form.reset();
      loadBounties();
      alert(`Bounty created and registered with Algorand escrow! App ID: ${data.app_id}`);
    } catch (err) {
      alert("Error creating bounty: " + err.message);
    }
  });
}

// Qmoosa Algo ($QALGO) Token Tools
function initTokenTools() {
  const maxSupplyEl = document.getElementById("tokenMaxSupply");
  const circulatingEl = document.getElementById("tokenCirculating");
  const burnedEl = document.getElementById("tokenBurned");
  const assetIdEl = document.getElementById("tokenAssetId");

  const faucetAddressInput = document.getElementById("faucetAddress");
  const faucetRoleSelect = document.getElementById("faucetRole");
  const claimFaucetBtn = document.getElementById("claimFaucetBtn");
  const faucetResultBox = document.getElementById("faucetResultBox");

  const exchangeServiceSelect = document.getElementById("exchangeServiceSelect");
  const exchangeAddressInput = document.getElementById("exchangeAddress");
  const exchangeServiceBtn = document.getElementById("exchangeServiceBtn");
  const exchangeResultBox = document.getElementById("exchangeResultBox");

  async function loadTokenMetrics() {
    try {
      const res = await fetch("/api/token/metrics");
      const data = await res.json();
      if (maxSupplyEl) maxSupplyEl.textContent = `${(data.max_supply_whole / 1e12).toFixed(2)}T QALGO`;
      if (circulatingEl) circulatingEl.textContent = `${(data.circulating_whole / 1e6).toFixed(2)}M QALGO`;
      if (burnedEl) burnedEl.textContent = `${(data.total_burned_whole / 1e6).toFixed(2)}M QALGO`;
      if (assetIdEl) assetIdEl.textContent = `#${data.asset_id}`;
    } catch (e) {
      console.warn("Could not load token metrics", e);
    }
  }

  loadTokenMetrics();

  // Faucet Allowance Handler
  if (claimFaucetBtn) {
    claimFaucetBtn.addEventListener("click", async () => {
      let addr = faucetAddressInput.value.trim();
      if (!addr) {
        const genAddr = document.getElementById("genAddress")?.value;
        if (genAddr) {
          addr = genAddr;
          faucetAddressInput.value = genAddr;
        } else {
          addr = "MW6XFO4NJPVM4DW2VO3NGD3NBSOMEBVLQOVLNGAJOHASMDLGZBUJPOWWIA";
          faucetAddressInput.value = addr;
        }
      }

      claimFaucetBtn.disabled = true;
      claimFaucetBtn.textContent = "Disbursing Allowance...";
      faucetResultBox.textContent = "Submitting participant transaction allowance to Algorand...";

      try {
        const res = await fetch("/api/token/faucet", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            recipient_address: addr,
            role: faucetRoleSelect.value,
          }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Faucet claim failed");
        faucetResultBox.textContent = JSON.stringify(data, null, 2);
        loadTokenMetrics();
        alert(`Success! ${data.amount_qalgo} QALGO credited for transaction gas & participation.`);
      } catch (err) {
        faucetResultBox.textContent = "Error: " + err.message;
      } finally {
        claimFaucetBtn.disabled = false;
        claimFaucetBtn.textContent = "Claim QALGO Allowance";
      }
    });
  }

  // Token Service Exchange Handler
  if (exchangeServiceBtn) {
    exchangeServiceBtn.addEventListener("click", async () => {
      let addr = exchangeAddressInput.value.trim();
      if (!addr) {
        const genAddr = document.getElementById("genAddress")?.value;
        if (genAddr) {
          addr = genAddr;
          exchangeAddressInput.value = genAddr;
        } else {
          addr = "MW6XFO4NJPVM4DW2VO3NGD3NBSOMEBVLQOVLNGAJOHASMDLGZBUJPOWWIA";
          exchangeAddressInput.value = addr;
        }
      }

      exchangeServiceBtn.disabled = true;
      exchangeServiceBtn.textContent = "Exchanging Tokens...";
      exchangeResultBox.textContent = "Executing token burn & service unlock...";

      try {
        const res = await fetch("/api/token/exchange", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_address: addr,
            service_key: exchangeServiceSelect.value,
          }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Exchange failed");
        exchangeResultBox.textContent = JSON.stringify(data, null, 2);
        loadTokenMetrics();
        alert(`Service Unlocked! ${data.qalgo_exchanged} QALGO exchanged (${data.tokens_burned} burned). Access token granted.`);
      } catch (err) {
        exchangeResultBox.textContent = "Error: " + err.message;
      } finally {
        exchangeServiceBtn.disabled = false;
        exchangeServiceBtn.textContent = "Exchange Tokens & Unlock Service";
      }
    });
  }
}

function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
