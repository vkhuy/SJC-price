const DATA_CANDIDATES = ["./data/sjc_final.csv", "../data/gold_sjc/sjc_final.csv"]

const state = {
  unit: "luong",
  range: "all",
}

let rawData = []
let chart

function parseCsv(text) {
  const lines = text.trim().split(/\r?\n/)
  if (lines.length <= 1) return []

  const rows = []
  for (let i = 1; i < lines.length; i += 1) {
    const [timestamp, buyStr, sellStr] = lines[i].split(",")
    const date = new Date(timestamp)
    const buy = Number(buyStr)
    const sell = Number(sellStr)

    if (!Number.isNaN(date.getTime()) && Number.isFinite(buy) && Number.isFinite(sell)) {
      rows.push({ date, buy, sell })
    }
  }

  return rows.sort((a, b) => a.date - b.date)
}

async function loadData() {
  for (const path of DATA_CANDIDATES) {
    try {
      const response = await fetch(path, { cache: "no-store" })
      if (!response.ok) continue

      const text = await response.text()
      const parsed = parseCsv(text)
      if (parsed.length > 0) {
        return { parsed, sourcePath: path }
      }
    } catch (error) {
      console.warn(`Cannot load ${path}`, error)
    }
  }

  throw new Error("CSV data not found")
}

function convertPrice(value, unit) {
  if (unit === "gram") {
    return (value * 1_000_000) / 37.5
  }
  return value
}

function formatValue(value, unit, compact = false) {
  if (!Number.isFinite(value)) return "-"

  if (unit === "gram") {
    return new Intl.NumberFormat("en-US", {
      notation: compact ? "compact" : "standard",
      maximumFractionDigits: compact ? 1 : 0,
    }).format(value) + " VND"
  }

  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value) + " mil VND"
}

function formatDate(date, short = false) {
  if (!(date instanceof Date) || Number.isNaN(date.getTime())) return "-"

  return new Intl.DateTimeFormat("en-GB", {
    day: short ? "2-digit" : "numeric",
    month: short ? "2-digit" : "long",
    year: "numeric",
  }).format(date)
}

function addMonths(date, months) {
  const d = new Date(date)
  d.setMonth(d.getMonth() + months)
  return d
}

function addYears(date, years) {
  const d = new Date(date)
  d.setFullYear(d.getFullYear() + years)
  return d
}

function applyRange(data, range) {
  if (!data.length || range === "all") return data

  const latest = data[data.length - 1].date
  let start = new Date(latest)

  if (range === "1m") start = addMonths(latest, -1)
  if (range === "3m") start = addMonths(latest, -3)
  if (range === "6m") start = addMonths(latest, -6)
  if (range === "1y") start = addYears(latest, -1)
  if (range === "3y") start = addYears(latest, -3)
  if (range === "5y") start = addYears(latest, -5)

  const filtered = data.filter((item) => item.date >= start)
  return filtered.length ? filtered : data
}

function findSnapshotByDays(data, dayCount) {
  if (!data.length) return null
  const latest = data[data.length - 1]
  const targetTs = latest.date.getTime() - dayCount * 24 * 60 * 60 * 1000

  for (let i = data.length - 1; i >= 0; i -= 1) {
    if (data[i].date.getTime() <= targetTs) return data[i]
  }

  return data[0]
}

function updateStats(data) {
  const latest = data[data.length - 1]
  const snapshot30 = findSnapshotByDays(data, 30)

  const latestBuy = convertPrice(latest.buy, state.unit)
  const latestSell = convertPrice(latest.sell, state.unit)
  const spread = latestSell - latestBuy

  document.getElementById("latestBuy").textContent = formatValue(latestBuy, state.unit)
  document.getElementById("latestSell").textContent = formatValue(latestSell, state.unit)
  document.getElementById("latestSpread").textContent = formatValue(spread, state.unit)

  const delta30Raw = convertPrice(latest.sell, state.unit) - convertPrice(snapshot30.sell, state.unit)
  const delta30 = (delta30Raw >= 0 ? "+" : "") + formatValue(delta30Raw, state.unit)
  document.getElementById("change30d").textContent = delta30

  document.getElementById("lastUpdated").textContent = `Last updated: ${formatDate(latest.date)}`
}

function updateRangeText(data) {
  const first = data[0]
  const last = data[data.length - 1]
  const msg = `${formatDate(first.date, true)} - ${formatDate(last.date, true)} (${data.length} data points)`
  document.getElementById("chartRangeLabel").textContent = msg
}

function buildDataset(data) {
  return {
    buy: data.map((d) => ({
      x: d.date.getTime(),
      y: convertPrice(d.buy, state.unit),
    })),
    sell: data.map((d) => ({
      x: d.date.getTime(),
      y: convertPrice(d.sell, state.unit),
    })),
  }
}

function tickLabel(ms) {
  const date = new Date(Number(ms))
  if (state.range === "1m" || state.range === "3m" || state.range === "6m") {
    return new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "2-digit" }).format(date)
  }

  if (state.range === "1y" || state.range === "3y") {
    return new Intl.DateTimeFormat("en-GB", { month: "2-digit", year: "2-digit" }).format(date)
  }

  return new Intl.DateTimeFormat("en-GB", { year: "numeric" }).format(date)
}

function renderChart() {
  const filtered = applyRange(rawData, state.range)
  updateStats(rawData)
  updateRangeText(filtered)

  const data = buildDataset(filtered)

  if (!chart) {
    const ctx = document.getElementById("sjcChart")

    chart = new Chart(ctx, {
      type: "line",
      data: {
        datasets: [
          {
            label: "Buy price",
            data: data.buy,
            parsing: false,
            borderColor: "#2f7f6f",
            backgroundColor: "rgba(47, 127, 111, 0.10)",
            borderWidth: 2,
            pointRadius: 0,
            fill: true,
            tension: 0.2,
          },
          {
            label: "Sell price",
            data: data.sell,
            parsing: false,
            borderColor: "#b7543b",
            backgroundColor: "rgba(183, 84, 59, 0.08)",
            borderWidth: 2,
            pointRadius: 0,
            fill: true,
            tension: 0.2,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: "index",
          intersect: false,
        },
        plugins: {
          legend: {
            labels: {
              color: "#56452f",
              usePointStyle: true,
              pointStyle: "line",
              font: {
                family: "Manrope",
                weight: 700,
              },
            },
          },
          tooltip: {
            backgroundColor: "rgba(38, 31, 21, 0.92)",
            titleFont: {
              family: "Fraunces",
              weight: "600",
            },
            bodyFont: {
              family: "Manrope",
            },
            callbacks: {
              title(items) {
                if (!items.length) return ""
                return formatDate(new Date(items[0].parsed.x))
              },
              label(context) {
                const value = context.parsed.y
                return `${context.dataset.label}: ${formatValue(value, state.unit)}`
              },
            },
          },
        },
        scales: {
          x: {
            type: "linear",
            grid: {
              display: false,
            },
            ticks: {
              color: "#736146",
              maxRotation: 0,
              autoSkip: true,
              maxTicksLimit: 8,
              callback(value) {
                return tickLabel(value)
              },
            },
          },
          y: {
            grid: {
              color: "rgba(115, 97, 70, 0.13)",
            },
            ticks: {
              color: "#736146",
              callback(value) {
                return formatValue(Number(value), state.unit, true)
              },
            },
          },
        },
      },
    })
    return
  }

  chart.data.datasets[0].data = data.buy
  chart.data.datasets[1].data = data.sell
  chart.update()
}

function setActiveButton(containerId, attr, value) {
  const root = document.getElementById(containerId)
  root.querySelectorAll("button").forEach((button) => {
    button.classList.toggle("active", button.getAttribute(attr) === value)
  })
}

function bindEvents() {
  document.getElementById("rangeButtons").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-range]")
    if (!button) return

    state.range = button.getAttribute("data-range")
    setActiveButton("rangeButtons", "data-range", state.range)
    renderChart()
  })

  document.getElementById("unitButtons").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-unit]")
    if (!button) return

    state.unit = button.getAttribute("data-unit")
    setActiveButton("unitButtons", "data-unit", state.unit)
    renderChart()
  })
}

async function main() {
  try {
    const { parsed, sourcePath } = await loadData()
    rawData = parsed
    bindEvents()
    renderChart()
    console.info(`Loaded ${rawData.length} rows from ${sourcePath}`)
  } catch (error) {
    console.error(error)
    document.getElementById("chartRangeLabel").textContent = "Unable to load CSV data"
  }
}

main()
