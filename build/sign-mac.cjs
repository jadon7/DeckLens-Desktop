const { signAsync } = require('@electron/osx-sign');

module.exports = async function signMac(configuration) {
  const identity = process.env.DECKLENS_MAC_SIGN_IDENTITY || configuration.identity;
  await signAsync({
    ...configuration,
    identity
  });
};
