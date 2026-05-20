// Sunbird RC connection config
export interface SunbirdConfig {
    sunbirdUrl: string
    keycloakUrl: string
    clientId: string
    clientSecret: string
    osidAttributeId: string // DHIS2 attribute to store Sunbird OSID
}

// Field mapping for transformation
export interface FieldMapping {
    source: string
    target: string
    required?: boolean
    constantValue?: string // For constant/static values
}

// Entity mapping - maps org unit groups to Sunbird entity type
export interface EntityMapping {
    id: string
    entityType: string
    orgUnitGroupIds: string[]
    fieldMappings: FieldMapping[]
}

// Org unit group from DHIS2
export interface OrgUnitGroup {
    id: string
    displayName: string
    code: string
}

// Facility org unit record for display
export interface FacilityRecord {
    id: string
    name: string
    code: string
    location: string // Hierarchy: County > District > Community
    coordinates?: { lon: number; lat: number }
    syncStatus: 'pending' | 'synced' | 'error'
    osid?: string
    errorMessage?: string // Error message from last sync attempt
}

// Sync stats
export interface SyncStats {
    total: number
    synced: number
    pending: number
    error: number
    lastSync?: string
}

// Available source fields for field mapping
// Note: GeoJSON coordinates are [longitude, latitude]
export const SOURCE_FIELDS = [
    { value: '$constant', label: '-- Constant Value --' },
    { value: 'id', label: 'Org Unit ID' },
    { value: 'name', label: 'Name' },
    { value: 'code', label: 'Code' },
    { value: 'shortName', label: 'Short Name' },
    { value: 'geometry.coordinates[1]', label: 'Latitude' },
    { value: 'geometry.coordinates[0]', label: 'Longitude' },
    { value: 'openingDate', label: 'Opening Date' },
    { value: 'parent.name', label: 'Parent Name' },
    { value: 'parent[level=2].name', label: 'County (Level 2)' },
    { value: 'parent[level=3].name', label: 'District (Level 3)' },
    { value: 'parent[level=4].name', label: 'Community (Level 4)' },
    { value: 'organisationUnitGroup.name', label: 'Facility Type (Group Name)' },
    { value: 'organisationUnitGroup.code', label: 'Facility Type (Group Code)' },
]
