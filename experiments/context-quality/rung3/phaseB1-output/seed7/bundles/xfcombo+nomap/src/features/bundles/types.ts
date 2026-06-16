export interface BundleDto {
    id: string;
    name: string;
    description?: string;
    price?: number;
    originalPrice?: number;
    discountPercent?: number;
    itemsCount?: number;
    imageUrl?: string;
    active: boolean;
    createdAt: string;
    updatedAt: string;
}
