import i18n from '@dhis2/d2-i18n'
import {
    Card,
    InputField,
    Button,
    NoticeBox,
    CircularLoader,
    Field,
    SingleSelect,
    SingleSelectOption,
    Transfer,
    IconAdd16,
    IconDelete16,
    IconEdit16,
    Divider,
    Tag,
    Modal,
    ModalTitle,
    ModalContent,
    ModalActions,
    ButtonStrip,
    DataTable,
    DataTableHead,
    DataTableBody,
    DataTableRow,
    DataTableCell,
    DataTableColumnHeader,
} from '@dhis2/ui'
import React, { FC, useState, useEffect, useMemo } from 'react'
import type { EntityMapping, FieldMapping, OrgUnitGroup } from '@/types'
import { SOURCE_FIELDS } from '@/types'
import { useSunbirdSchema, SchemaField } from '@/hooks'
import classes from './Mappings.module.css'

interface MappingsProps {
    entityMappings: EntityMapping[]
    orgUnitGroups: OrgUnitGroup[]
    sunbirdUrl?: string
    loading?: boolean
    saving?: boolean
    onSaveMapping: (mapping: EntityMapping) => void
    onDeleteMapping: (id: string) => void
}

const Mappings: FC<MappingsProps> = ({
    entityMappings,
    orgUnitGroups,
    sunbirdUrl = '',
    loading = false,
    saving = false,
    onSaveMapping,
    onDeleteMapping,
}) => {
    const [showMappingModal, setShowMappingModal] = useState(false)
    const [editingMapping, setEditingMapping] = useState<EntityMapping | null>(null)
    const { fields: schemaFields, loading: schemaLoading, error: schemaError, fetchSchema, clearSchema } = useSunbirdSchema()

    const handleAddMapping = () => {
        setEditingMapping({
            id: `em-${Date.now()}`,
            entityType: '',
            orgUnitGroupIds: [],
            fieldMappings: [
                { source: 'name', target: 'facilityName', required: true },
                { source: 'code', target: 'facilityCode', required: false },
            ],
        })
        setShowMappingModal(true)
    }

    const handleEditMapping = (mapping: EntityMapping) => {
        setEditingMapping({ ...mapping })
        setShowMappingModal(true)
        // Auto-fetch schema when editing if entity type exists
        if (mapping.entityType && sunbirdUrl) {
            fetchSchema(sunbirdUrl, mapping.entityType)
        }
    }

    const handleDeleteMapping = (id: string) => {
        if (confirm(i18n.t('Are you sure you want to delete this mapping?'))) {
            onDeleteMapping(id)
        }
    }

    const handleSaveMapping = () => {
        if (!editingMapping) return

        if (!editingMapping.entityType) {
            alert(i18n.t('Entity Type is required'))
            return
        }
        if (editingMapping.orgUnitGroupIds.length === 0) {
            alert(i18n.t('At least one Org Unit Group is required'))
            return
        }

        onSaveMapping(editingMapping)
        setShowMappingModal(false)
        setEditingMapping(null)
    }

    const getGroupName = (groupId: string): string => {
        const group = orgUnitGroups.find((g) => g.id === groupId)
        return group?.displayName || groupId
    }

    if (loading) {
        return (
            <div className={classes.loadingContainer}>
                <CircularLoader />
            </div>
        )
    }

    return (
        <div className={classes.container}>
            <h2>{i18n.t('Entity Mappings')}</h2>

            <NoticeBox title={i18n.t('Configure Sync Mappings')}>
                {i18n.t(
                    'Map Org Unit Groups to Sunbird Entity Types. Each mapping defines which facilities sync to which Sunbird entity and how fields are transformed.'
                )}
            </NoticeBox>

            <div className={classes.mappingsSection}>
                <div className={classes.mappingsHeader}>
                    <Button icon={<IconAdd16 />} onClick={handleAddMapping} primary>
                        {i18n.t('Add Mapping')}
                    </Button>
                </div>

                {entityMappings.length === 0 ? (
                    <Card className={classes.emptyCard}>
                        <NoticeBox title={i18n.t('No Mappings Configured')}>
                            {i18n.t(
                                'Click "Add Mapping" to configure which Org Unit Groups sync to which Sunbird Entity Types.'
                            )}
                        </NoticeBox>
                    </Card>
                ) : (
                    <div className={classes.mappingsList}>
                        {entityMappings.map((mapping) => (
                            <Card key={mapping.id} className={classes.mappingCard}>
                                <div className={classes.mappingHeader}>
                                    <div>
                                        <strong>{mapping.entityType}</strong>
                                        <div className={classes.mappingGroups}>
                                            {mapping.orgUnitGroupIds.map((gid) => (
                                                <Tag key={gid} neutral>
                                                    {getGroupName(gid)}
                                                </Tag>
                                            ))}
                                        </div>
                                    </div>
                                    <div className={classes.mappingActions}>
                                        <Button
                                            small
                                            icon={<IconEdit16 />}
                                            onClick={() => handleEditMapping(mapping)}
                                        >
                                            {i18n.t('Edit')}
                                        </Button>
                                        <Button
                                            small
                                            destructive
                                            icon={<IconDelete16 />}
                                            onClick={() => handleDeleteMapping(mapping.id)}
                                        >
                                            {i18n.t('Delete')}
                                        </Button>
                                    </div>
                                </div>
                                <Divider />
                                <div className={classes.mappingFieldCount}>
                                    {i18n.t('{{count}} field mappings', {
                                        count: mapping.fieldMappings.length,
                                    })}
                                </div>
                                <div className={classes.fieldMappingPreview}>
                                    {mapping.fieldMappings.slice(0, 3).map((fm, idx) => (
                                        <span key={idx} className={classes.fieldPreview}>
                                            {fm.source} &rarr; {fm.target}
                                        </span>
                                    ))}
                                    {mapping.fieldMappings.length > 3 && (
                                        <span className={classes.fieldPreview}>
                                            +{mapping.fieldMappings.length - 3} more
                                        </span>
                                    )}
                                </div>
                            </Card>
                        ))}
                    </div>
                )}
            </div>

            {showMappingModal && editingMapping && (
                <EntityMappingModal
                    mapping={editingMapping}
                    orgUnitGroups={orgUnitGroups}
                    existingMappings={entityMappings}
                    sunbirdUrl={sunbirdUrl}
                    schemaFields={schemaFields}
                    schemaLoading={schemaLoading}
                    schemaError={schemaError}
                    onFetchSchema={fetchSchema}
                    onClearSchema={clearSchema}
                    saving={saving}
                    onSave={handleSaveMapping}
                    onCancel={() => {
                        setShowMappingModal(false)
                        setEditingMapping(null)
                        clearSchema()
                    }}
                    onChange={setEditingMapping}
                />
            )}
        </div>
    )
}

interface EntityMappingModalProps {
    mapping: EntityMapping
    orgUnitGroups: OrgUnitGroup[]
    existingMappings: EntityMapping[]
    sunbirdUrl: string
    schemaFields: SchemaField[]
    schemaLoading: boolean
    schemaError: string | null
    onFetchSchema: (sunbirdUrl: string, entityType: string) => Promise<void>
    onClearSchema: () => void
    saving?: boolean
    onSave: () => void
    onCancel: () => void
    onChange: (mapping: EntityMapping) => void
}

const EntityMappingModal: FC<EntityMappingModalProps> = ({
    mapping,
    orgUnitGroups,
    existingMappings,
    sunbirdUrl,
    schemaFields,
    schemaLoading,
    schemaError,
    onFetchSchema,
    onClearSchema,
    saving = false,
    onSave,
    onCancel,
    onChange,
}) => {
    const usedGroupIds = existingMappings
        .filter((m) => m.id !== mapping.id)
        .flatMap((m) => m.orgUnitGroupIds)

    const availableGroups = orgUnitGroups.filter((g) => !usedGroupIds.includes(g.id))

    // Get already used target fields (to filter from dropdown)
    const usedTargetFields = useMemo(() => {
        return mapping.fieldMappings.map((fm) => fm.target).filter(Boolean)
    }, [mapping.fieldMappings])

    // Calculate unmapped required fields
    const unmappedRequiredFields = useMemo(() => {
        if (schemaFields.length === 0) return []
        const requiredFields = schemaFields.filter((f) => f.required)
        return requiredFields.filter((f) => !usedTargetFields.includes(f.path))
    }, [schemaFields, usedTargetFields])

    // Get available target fields for a specific row (exclude already used, except current)
    const getAvailableTargetFields = (currentTarget: string) => {
        return schemaFields.filter(
            (f) => f.path === currentTarget || !usedTargetFields.includes(f.path)
        )
    }

    const handleGroupChange = (selected: string[]) => {
        onChange({ ...mapping, orgUnitGroupIds: selected })
    }

    const handleAddFieldMapping = () => {
        onChange({
            ...mapping,
            fieldMappings: [...mapping.fieldMappings, { source: '', target: '', required: false }],
        })
    }

    const handleFieldMappingChange = (index: number, field: keyof FieldMapping, value: any) => {
        const newMappings = [...mapping.fieldMappings]
        newMappings[index] = { ...newMappings[index], [field]: value }
        onChange({ ...mapping, fieldMappings: newMappings })
    }

    const handleRemoveFieldMapping = (index: number) => {
        const newMappings = mapping.fieldMappings.filter((_, i) => i !== index)
        onChange({ ...mapping, fieldMappings: newMappings })
    }

    const handleFetchSchema = () => {
        if (!mapping.entityType) {
            alert(i18n.t('Please enter an Entity Type first'))
            return
        }
        if (!sunbirdUrl) {
            alert(i18n.t('Sunbird URL is not configured. Please configure it in Settings.'))
            return
        }
        onFetchSchema(sunbirdUrl, mapping.entityType)
    }

    const handleEntityTypeChange = (value: string) => {
        onChange({ ...mapping, entityType: value })
        // Clear schema when entity type changes
        onClearSchema()
    }

    return (
        <Modal large onClose={onCancel}>
            <ModalTitle>
                {mapping.entityType
                    ? i18n.t('Edit Entity Mapping: {{type}}', { type: mapping.entityType })
                    : i18n.t('New Entity Mapping')}
            </ModalTitle>
            <ModalContent>
                <div className={classes.modalContent}>
                    <div className={classes.entityTypeRow}>
                        <div className={classes.entityTypeInput}>
                            <InputField
                                label={i18n.t('Sunbird Entity Type')}
                                value={mapping.entityType}
                                onChange={({ value }) => handleEntityTypeChange(value || '')}
                                placeholder="WaterFacility"
                                helpText={i18n.t('The entity type name in Sunbird RC')}
                                required
                            />
                        </div>
                        <div className={classes.fetchSchemaButton}>
                            <Button
                                onClick={handleFetchSchema}
                                loading={schemaLoading}
                                disabled={!mapping.entityType || !sunbirdUrl}
                            >
                                {i18n.t('Fetch Schema')}
                            </Button>
                        </div>
                    </div>

                    {schemaError && (
                        <NoticeBox error title={i18n.t('Schema Error')}>
                            {schemaError}
                        </NoticeBox>
                    )}

                    {schemaFields.length > 0 && (
                        <NoticeBox
                            title={i18n.t('Schema Loaded')}
                            warning={unmappedRequiredFields.length > 0}
                        >
                            {i18n.t('{{count}} fields available from Sunbird schema.', {
                                count: schemaFields.length,
                            })}
                            {unmappedRequiredFields.length > 0 && (
                                <span>
                                    {' '}
                                    <strong>
                                        {i18n.t('Required fields left: {{count}}', {
                                            count: unmappedRequiredFields.length,
                                        })}
                                    </strong>
                                    {' ('}
                                    {unmappedRequiredFields.map((f) => f.path).join(', ')}
                                    {')'}
                                </span>
                            )}
                            {unmappedRequiredFields.length === 0 && (
                                <span> {i18n.t('All required fields are mapped.')}</span>
                            )}
                        </NoticeBox>
                    )}

                    <div className={classes.transferSection}>
                        <Field label={i18n.t('Org Unit Groups')} required>
                            <Transfer
                                selected={mapping.orgUnitGroupIds}
                                onChange={({ selected }) => handleGroupChange(selected)}
                                options={availableGroups.map((g) => ({
                                    value: g.id,
                                    label: g.displayName,
                                }))}
                                selectedEmptyComponent={
                                    <p style={{ textAlign: 'center', padding: '8px' }}>
                                        {i18n.t('Select groups from the left')}
                                    </p>
                                }
                                leftHeader={<span>{i18n.t('Available Groups')}</span>}
                                rightHeader={<span>{i18n.t('Selected Groups')}</span>}
                                height="200px"
                            />
                        </Field>
                    </div>

                    <div className={classes.dividerSection}>
                        <Divider />
                    </div>

                    <div className={classes.fieldMappingsHeader}>
                        <h4>{i18n.t('Field Mappings')}</h4>
                        <Button small icon={<IconAdd16 />} onClick={handleAddFieldMapping}>
                            {i18n.t('Add Field')}
                        </Button>
                    </div>

                    <DataTable>
                        <DataTableHead>
                            <DataTableRow>
                                <DataTableColumnHeader>{i18n.t('DHIS2 Source')}</DataTableColumnHeader>
                                <DataTableColumnHeader>{i18n.t('Sunbird Target')}</DataTableColumnHeader>
                                <DataTableColumnHeader width="80px">{i18n.t('Actions')}</DataTableColumnHeader>
                            </DataTableRow>
                        </DataTableHead>
                        <DataTableBody>
                            {mapping.fieldMappings.map((fm, index) => (
                                <DataTableRow key={index}>
                                    <DataTableCell>
                                        <div className={classes.sourceFieldCell}>
                                            <SingleSelect
                                                selected={fm.source}
                                                onChange={({ selected }) =>
                                                    handleFieldMappingChange(index, 'source', selected)
                                                }
                                                placeholder={i18n.t('Select source')}
                                                dense
                                            >
                                                {SOURCE_FIELDS.map((f) => (
                                                    <SingleSelectOption
                                                        key={f.value}
                                                        value={f.value}
                                                        label={f.label}
                                                    />
                                                ))}
                                            </SingleSelect>
                                            {fm.source === '$constant' && (
                                                <InputField
                                                    value={fm.constantValue || ''}
                                                    onChange={({ value }) =>
                                                        handleFieldMappingChange(index, 'constantValue', value || '')
                                                    }
                                                    placeholder={i18n.t('Enter constant value')}
                                                    dense
                                                />
                                            )}
                                        </div>
                                    </DataTableCell>
                                    <DataTableCell>
                                        {schemaFields.length > 0 ? (
                                            <SingleSelect
                                                selected={fm.target}
                                                onChange={({ selected }) =>
                                                    handleFieldMappingChange(index, 'target', selected)
                                                }
                                                placeholder={i18n.t('Select target field')}
                                                dense
                                            >
                                                {getAvailableTargetFields(fm.target).map((f) => (
                                                    <SingleSelectOption
                                                        key={f.path}
                                                        value={f.path}
                                                        label={`${f.path}${f.required ? ' *' : ''}`}
                                                    />
                                                ))}
                                            </SingleSelect>
                                        ) : (
                                            <InputField
                                                value={fm.target}
                                                onChange={({ value }) =>
                                                    handleFieldMappingChange(index, 'target', value || '')
                                                }
                                                placeholder="facilityName"
                                                dense
                                            />
                                        )}
                                    </DataTableCell>
                                    <DataTableCell>
                                        <Button
                                            small
                                            destructive
                                            icon={<IconDelete16 />}
                                            onClick={() => handleRemoveFieldMapping(index)}
                                        />
                                    </DataTableCell>
                                </DataTableRow>
                            ))}
                        </DataTableBody>
                    </DataTable>
                </div>
            </ModalContent>
            <ModalActions>
                <ButtonStrip end>
                    <Button onClick={onCancel}>{i18n.t('Cancel')}</Button>
                    <Button primary onClick={onSave} loading={saving}>
                        {i18n.t('Save Mapping')}
                    </Button>
                </ButtonStrip>
            </ModalActions>
        </Modal>
    )
}

export default Mappings
