import { useEffect, useState } from "react";
import { api } from "../api";
import { useUser } from "../user";

type Pack = {
  id: string;
  name: string;
  credits: number;
  amount: number;
  amount_display: string;
  blurb: string;
};

function loadScript(src: string): Promise<boolean> {
  return new Promise((resolve) => {
    if (document.querySelector(`script[src="${src}"]`)) return resolve(true);
    const s = document.createElement("script");
    s.src = src;
    s.onload = () => resolve(true);
    s.onerror = () => resolve(false);
    document.body.appendChild(s);
  });
}

/**
 * Pricing + paywall. Shows credit packs and triggers the provider checkout.
 * Credits are granted server-side by a verified webhook — this UI only starts
 * the payment. `onClose` closes the paywall; `reason` shows a paywall message.
 */
export default function Pricing({
  onClose,
  reason,
  onPaid,
}: {
  onClose?: () => void;
  reason?: string;
  onPaid?: () => void;
}) {
  const { authed } = useUser();
  const [packs, setPacks] = useState<Pack[]>([]);
  const [providers, setProviders] = useState<Record<string, boolean>>({});
  const [activeProvider, setActiveProvider] = useState("razorpay");
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState("");
  const [devPay, setDevPay] = useState(false);

  useEffect(() => {
    api
      .plans()
      .then((d) => {
        setPacks(d.packs);
        setProviders(d.providers_configured || {});
        setActiveProvider(d.active_provider || "razorpay");
        setDevPay(!!d.dev_payments_enabled);
      })
      .catch(() => {});
  }, []);

  const testPay = async (packId: string) => {
    setMsg("");
    try {
      await api.devGrant(packId);
      setMsg("✅ Test credits added! (dev mode)");
      setTimeout(() => onPaid?.(), 800);
    } catch (e: any) {
      setMsg(e.message || "Test payment failed.");
    }
  };

  const anyProviderReady =
    providers.razorpay || providers.cashfree || false;

  const buy = async (packId: string) => {
    if (!authed) {
      setMsg("Please log in to purchase credits.");
      return;
    }
    setBusy(packId);
    setMsg("");
    try {
      const order = await api.createOrder(packId, activeProvider);
      if (order.provider === "razorpay") {
        const ok = await loadScript(
          "https://checkout.razorpay.com/v1/checkout.js"
        );
        if (!ok) throw new Error("Could not load Razorpay checkout.");
        const rzp = new (window as any).Razorpay({
          key: order.key_id,
          amount: order.amount,
          currency: order.currency,
          name: "AI Interviewer",
          description: "Interview credits",
          order_id: order.provider_order_id,
          handler: () => {
            // Payment captured on Razorpay; credits are granted by the webhook.
            setMsg("Payment received! Credits will appear in a moment.");
            setTimeout(() => onPaid?.(), 1500);
          },
          theme: { color: "#6366f1" },
        });
        rzp.open();
      } else if (order.provider === "cashfree") {
        const ok = await loadScript("https://sdk.cashfree.com/js/v3/cashfree.js");
        if (!ok) throw new Error("Could not load Cashfree checkout.");
        const cashfree = (window as any).Cashfree({
          mode: order.cf_env === "production" ? "production" : "sandbox",
        });
        await cashfree.checkout({
          paymentSessionId: order.payment_session_id,
          redirectTarget: "_modal",
        });
        setMsg("Payment submitted! Credits will appear once confirmed.");
        setTimeout(() => onPaid?.(), 1500);
      }
    } catch (e: any) {
      setMsg(e.message || "Could not start checkout.");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
      <div className="w-full max-w-2xl rounded-2xl bg-[#0b1020] border border-white/10 p-6 max-h-[90vh] overflow-y-auto">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-2xl font-bold">Get more interviews</h2>
            {reason && <p className="mt-1 text-yellow-300 text-sm">{reason}</p>}
            <p className="mt-1 text-gray-400 text-sm">
              Buy credits — each credit is one full mock interview with grading,
              hints, code execution and the design whiteboard.
            </p>
          </div>
          {onClose && (
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-white text-xl leading-none"
            >
              ×
            </button>
          )}
        </div>

        {!anyProviderReady && (
          <div className="mt-4 rounded-xl border border-yellow-500/40 bg-yellow-500/10 px-4 py-3 text-sm text-yellow-200">
            ⚠️ Payments aren't configured on the server yet. Add your Razorpay or
            Cashfree keys to enable checkout (test mode works with test cards).
          </div>
        )}

        <div className="mt-5 grid sm:grid-cols-3 gap-3">
          {packs.map((p) => (
            <div
              key={p.id}
              className="rounded-2xl bg-white/5 border border-white/10 p-4 flex flex-col"
            >
              <div className="font-semibold text-lg">{p.name}</div>
              <div className="text-3xl font-bold mt-1">{p.amount_display}</div>
              <div className="text-sm text-gray-400 mt-1">{p.blurb}</div>
              <div className="text-xs text-brand-300 mt-2">
                {p.credits} interviews
              </div>
              <button
                onClick={() => buy(p.id)}
                disabled={busy === p.id || !anyProviderReady}
                className="mt-4 py-2 rounded-xl bg-brand-600 hover:bg-brand-500 font-medium text-sm disabled:opacity-50"
              >
                {busy === p.id ? "Starting…" : "Buy"}
              </button>
              {devPay && (
                <button
                  onClick={() => testPay(p.id)}
                  className="mt-2 py-1.5 rounded-lg bg-yellow-500/20 border border-yellow-500/40 text-yellow-200 text-xs hover:bg-yellow-500/30"
                >
                  🧪 Test-pay (no charge)
                </button>
              )}
            </div>
          ))}
        </div>

        {(providers.razorpay && providers.cashfree) && (
          <div className="mt-4 flex items-center gap-2 text-xs text-gray-400">
            Pay with:
            <button
              onClick={() => setActiveProvider("razorpay")}
              className={`px-2 py-1 rounded ${
                activeProvider === "razorpay" ? "bg-brand-600" : "bg-white/10"
              }`}
            >
              Razorpay
            </button>
            <button
              onClick={() => setActiveProvider("cashfree")}
              className={`px-2 py-1 rounded ${
                activeProvider === "cashfree" ? "bg-brand-600" : "bg-white/10"
              }`}
            >
              Cashfree
            </button>
          </div>
        )}

        {msg && <p className="mt-4 text-sm text-brand-300">{msg}</p>}
      </div>
    </div>
  );
}
