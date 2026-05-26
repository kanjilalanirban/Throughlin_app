// Runtime config: baked in at build time by the CD workflow from SSM.
//
// Local dev: set VITE_* in frontend/.env.local
// CI deploy: frontend-deploy.yml reads SSM and exports them at `pnpm build`

export const config = {
  apiUrl: import.meta.env.VITE_API_URL ?? "http://localhost:8000",
  cognito: {
    userPoolId: import.meta.env.VITE_COGNITO_USER_POOL_ID ?? "",
    clientId: import.meta.env.VITE_COGNITO_CLIENT_ID ?? "",
    region: import.meta.env.VITE_AWS_REGION ?? "ca-central-1",
  },
};

export function cognitoConfigured(): boolean {
  return !!(config.cognito.userPoolId && config.cognito.clientId);
}
