"""Privacy Policy and Terms of Service pages."""

PRIVACY_HTML = r'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Privacy Policy — Kandal</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #0f0c15; color: #f5ead6;
      -webkit-font-smoothing: antialiased;
      max-width: 640px; margin: 0 auto; padding: 2rem 1.5rem;
      line-height: 1.7;
    }
    a { color: #f5ead6; }
    h1 { font-size: 1.5rem; margin-bottom: 0.5rem; }
    h2 { font-size: 1.1rem; margin-top: 2rem; margin-bottom: 0.5rem; }
    p, li { color: rgba(245,234,214,0.75); font-size: 0.9rem; }
    ul { padding-left: 1.2rem; }
    .updated { font-size: 0.8rem; color: rgba(245,234,214,0.4); margin-bottom: 2rem; }
    .back { font-size: 0.85rem; display: inline-block; margin-bottom: 1.5rem; color: rgba(245,234,214,0.5); text-decoration: none; }
  </style>
</head>
<body>
  <a href="/" class="back">&larr; Back to Kandal</a>
  <h1>Privacy Policy</h1>
  <p class="updated">Last updated: April 6, 2026</p>

  <p>Kandal ("we", "us", "our") operates the kandal.app website and SMS-based matchmaking service. This policy explains how we collect, use, and protect your information.</p>

  <h2>1. Information We Collect</h2>
  <ul>
    <li><strong>Phone number:</strong> Used to identify your account and deliver SMS messages.</li>
    <li><strong>Profile information:</strong> Name, age, gender, city, and preferences you provide during onboarding.</li>
    <li><strong>Conversation data:</strong> Your responses during the profiling conversation, used to build your matchmaking profile.</li>
    <li><strong>Usage data:</strong> Basic server logs (timestamps, request metadata) for debugging and service reliability.</li>
  </ul>

  <h2>2. How We Use Your Information</h2>
  <ul>
    <li>To create and maintain your matchmaking profile.</li>
    <li>To compute compatibility scores and surface mutual matches.</li>
    <li>To send you SMS messages related to your profile and matches.</li>
    <li>To improve our matching algorithms and service quality.</li>
  </ul>

  <h2>3. SMS Messaging</h2>
  <p>By providing your phone number and consenting on our website, you agree to receive SMS messages from Kandal. These messages include profiling questions, match notifications, and service updates. Message frequency varies. Message and data rates may apply.</p>
  <p>You can opt out at any time by replying <strong>STOP</strong> to any message. Reply <strong>HELP</strong> for support. Upon opting out, we will stop sending SMS messages but retain your account data unless you request deletion.</p>

  <h2>4. Data Sharing</h2>
  <p>We do not sell your personal information. We share data only with:</p>
  <ul>
    <li><strong>Service providers:</strong> Twilio (SMS delivery), Supabase (database hosting), Anthropic (AI conversation processing), and Vercel (web hosting) — each bound by their own privacy policies.</li>
    <li><strong>Matched users:</strong> Only your first name and city are shared with a mutual match. Your phone number is never shared with other users.</li>
  </ul>

  <h2>5. Data Retention</h2>
  <p>We retain your data for as long as your account is active. You may request deletion of your data at any time by contacting us at customersupport@kandal.com.</p>

  <h2>6. Security</h2>
  <p>We use industry-standard measures to protect your data, including encrypted database connections, secure API keys, and HTTPS for all communications.</p>

  <h2>7. Changes</h2>
  <p>We may update this policy from time to time. Changes will be posted on this page with an updated date.</p>

  <h2>8. Contact</h2>
  <p>Questions? Email us at <a href="mailto:customersupport@kandal.com">customersupport@kandal.com</a>.</p>
</body>
</html>'''


TERMS_HTML = r'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Terms of Service — Kandal</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #0f0c15; color: #f5ead6;
      -webkit-font-smoothing: antialiased;
      max-width: 640px; margin: 0 auto; padding: 2rem 1.5rem;
      line-height: 1.7;
    }
    a { color: #f5ead6; }
    h1 { font-size: 1.5rem; margin-bottom: 0.5rem; }
    h2 { font-size: 1.1rem; margin-top: 2rem; margin-bottom: 0.5rem; }
    p, li { color: rgba(245,234,214,0.75); font-size: 0.9rem; }
    ul { padding-left: 1.2rem; }
    .updated { font-size: 0.8rem; color: rgba(245,234,214,0.4); margin-bottom: 2rem; }
    .back { font-size: 0.85rem; display: inline-block; margin-bottom: 1.5rem; color: rgba(245,234,214,0.5); text-decoration: none; }
  </style>
</head>
<body>
  <a href="/" class="back">&larr; Back to Kandal</a>
  <h1>Terms of Service</h1>
  <p class="updated">Last updated: April 6, 2026</p>

  <p>These terms govern your use of Kandal ("the Service"), operated by Kandal ("we", "us"). By using the Service, you agree to these terms.</p>

  <h2>1. Eligibility</h2>
  <p>You must be at least 18 years old to use Kandal. By signing up, you confirm that you meet this requirement.</p>

  <h2>2. Your Account</h2>
  <p>You are responsible for the information you provide. You agree to provide accurate, current information during onboarding. One account per phone number.</p>

  <h2>3. SMS Communications</h2>
  <p>By entering your phone number and checking the consent box on our website, you consent to receive recurring SMS messages from Kandal related to your matchmaking profile, including profiling questions, match notifications, and service updates.</p>
  <ul>
    <li>Message frequency varies based on your activity.</li>
    <li>Message and data rates may apply depending on your carrier plan.</li>
    <li>Reply <strong>STOP</strong> at any time to opt out of SMS messages.</li>
    <li>Reply <strong>HELP</strong> for support information.</li>
    <li>Compatible with all major US carriers.</li>
  </ul>

  <h2>4. Acceptable Use</h2>
  <p>You agree not to:</p>
  <ul>
    <li>Provide false or misleading information in your profile.</li>
    <li>Use the Service to harass, abuse, or harm others.</li>
    <li>Attempt to access other users' data or reverse-engineer the Service.</li>
    <li>Use the Service for any unlawful purpose.</li>
  </ul>

  <h2>5. Matches</h2>
  <p>Kandal uses AI-driven compatibility scoring to suggest matches. We do not guarantee match quality or outcomes. Matches are based on information you provide and algorithmic analysis.</p>

  <h2>6. Privacy</h2>
  <p>Your use of the Service is also governed by our <a href="/privacy">Privacy Policy</a>.</p>

  <h2>7. Termination</h2>
  <p>We may suspend or terminate your access at any time for violation of these terms. You may delete your account by contacting us at customersupport@kandal.com.</p>

  <h2>8. Disclaimer</h2>
  <p>The Service is provided "as is" without warranties of any kind. We are not liable for any damages arising from your use of the Service.</p>

  <h2>9. Changes</h2>
  <p>We may update these terms from time to time. Continued use of the Service after changes constitutes acceptance.</p>

  <h2>10. Contact</h2>
  <p>Questions? Email us at <a href="mailto:customersupport@kandal.com">customersupport@kandal.com</a>.</p>
</body>
</html>'''
