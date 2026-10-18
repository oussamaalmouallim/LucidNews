import { expect, test as base, type Page } from '@playwright/test'

/** The fixture administrator of scripts/e2e_server.py; the test server is the only place it exists. */
const ADMIN = { email: 'admin@e2e.test', password: 'e2e admin passphrase' }
const READER_PASSWORD = 'a reader passphrase'

const AI_NEWS = 'Un nouveau modèle de langage ouvert'
const CLOUD_NEWS = 'Nouvelle région cloud en Europe'

/** Every journey fails on a browser error: a Content-Security-Policy refusal, a crash, a 500. */
const test = base.extend<{ page: Page }>({
  page: async ({ page }, use) => {
    const errors: string[] = []
    page.on('console', (message) => {
      // A refusal the journey asks for (401 signed out, 403 admin only, 422 weak password) is an answer, not a fault.
      if (message.type() === 'error' && !/status of 4\d\d/.test(message.text())) errors.push(message.text())
    })
    page.on('pageerror', (error) => errors.push(error.message))
    await use(page)
    expect(errors).toEqual([])
  },
})

const uniqueEmail = () => `reader-${Date.now()}-${Math.floor(Math.random() * 1e6)}@e2e.test`

async function signIn(page: Page, email: string, password: string) {
  await page.goto('/sign-in?lang=fr')
  await page.getByLabel('Adresse e-mail').fill(email)
  await page.getByLabel('Mot de passe', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Se connecter', exact: true }).click()
}

async function signOut(page: Page) {
  await page.getByRole('button', { name: 'Menu du compte' }).click()
  await page.getByRole('button', { name: 'Se déconnecter' }).click()
  await expect(page).toHaveURL(/\/sign-in/)
}

test('a reader signs up, chooses a watch, reads their selection, is refused the administration, signs out', async ({ page }) => {
  const email = uniqueEmail()

  // Sign-up: no e-mail to confirm, the edition opens straight away.
  await page.goto('/?lang=fr')
  await expect(page).toHaveURL(/\/sign-in/)
  await page.getByRole('tab', { name: 'Créer un compte' }).click()
  await page.getByLabel('Adresse e-mail').fill(email)
  await page.getByLabel('Mot de passe', { exact: true }).fill(READER_PASSWORD)
  await page.getByRole('button', { name: 'Créer mon compte' }).click()
  await expect(page.getByText(AI_NEWS).first()).toBeVisible()
  await expect(page.getByText(CLOUD_NEWS).first()).toBeVisible()

  // Preferences: follow AI only, saved with the account.
  await page.getByRole('link', { name: 'Choisir mes domaines' }).click()
  const watch = page.getByRole('region', { name: 'Ma veille' })
  await watch.getByRole('button', { name: /IA \/ LLM \/ Agents/ }).click()
  await watch.getByRole('button', { name: 'Enregistrer ma veille' }).click()
  await expect(watch.getByRole('button', { name: 'Enregistré' })).toBeVisible()

  // Preview of "My selection": the cloud news is left out, the whole edition still has it.
  await page.getByRole('navigation', { name: 'Navigation principale' }).first().getByRole('link', { name: 'Édition' }).click()
  const view = page.getByRole('group', { name: 'Que montrer' })
  await expect(view.getByRole('button', { name: 'Ma sélection' })).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByText(AI_NEWS).first()).toBeVisible()
  await expect(page.getByText(CLOUD_NEWS)).toHaveCount(0)
  await view.getByRole('button', { name: 'Tout' }).click()
  await expect(page.getByText(CLOUD_NEWS).first()).toBeVisible()

  // The administration is not theirs: not in the navigation, explained on the screen, refused by the API.
  await expect(page.getByRole('link', { name: 'Réglages' })).toHaveCount(0)
  await page.goto('/settings?lang=fr')
  await expect(page.getByRole('heading', { name: 'Réservé à l’administration' })).toBeVisible()
  const settings = await page.request.get('/api/settings')
  expect(settings.status()).toBe(403)

  // Sign-out: the edition is closed again, and the preferences are still there at the next sign-in.
  await signOut(page)
  expect((await page.request.get('/api/editions')).status()).toBe(401)
  await signIn(page, email, READER_PASSWORD)
  await expect(page.getByRole('group', { name: 'Que montrer' }).getByRole('button', { name: 'Ma sélection' })).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByText(CLOUD_NEWS)).toHaveCount(0)
})

test('a wrong password is refused and says so', async ({ page }) => {
  await signIn(page, ADMIN.email, 'not the password')
  await expect(page.getByRole('alert')).toBeVisible()
  await expect(page).toHaveURL(/\/sign-in/)
})

test('a guessable password is refused at sign-up', async ({ page }) => {
  await page.goto('/sign-up?lang=fr')
  await page.getByLabel('Adresse e-mail').fill(uniqueEmail())
  await page.getByLabel('Mot de passe', { exact: true }).fill('password123')
  await page.getByRole('button', { name: 'Créer mon compte' }).click()
  await expect(page.getByRole('alert')).toBeVisible()
  await expect(page).toHaveURL(/\/sign-up/)
})

test('an administrator reaches the administration screens', async ({ page }) => {
  await signIn(page, ADMIN.email, ADMIN.password)
  const nav = page.getByRole('navigation', { name: 'Navigation principale' }).first()
  await expect(nav.getByRole('link', { name: 'Réglages' })).toBeVisible()
  await nav.getByRole('link', { name: 'Réglages' }).click()
  await expect(page.getByRole('heading', { name: 'Réservé à l’administration' })).toHaveCount(0)
  expect((await page.request.get('/api/settings')).status()).toBe(200)
  await signOut(page)
})

test('the built page carries its Content-Security-Policy', async ({ page }) => {
  await page.goto('/sign-in?lang=fr')
  const policy = await page.locator('meta[http-equiv="Content-Security-Policy"]').getAttribute('content')
  expect(policy).toContain("default-src 'self'")
  expect(policy).toContain("object-src 'none'")
})
