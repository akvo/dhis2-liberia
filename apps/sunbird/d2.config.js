/** @type {import('@dhis2/cli-app-scripts').D2Config} */
const config = {
    type: 'app',
    title: 'Sunbird',
    description: 'Sync management between DHIS2 and Sunbird RC',

    // Reserve DataStore namespace for this app
    dataStoreNamespace: 'sunbird-sync',

    // Custom authority for admin access
    customAuthorities: ['SUNBIRD_ADMIN'],

    entryPoints: {
        app: './src/App.tsx',
    },

    viteConfigExtensions: './viteConfigExtensions.mts',
}

module.exports = config
