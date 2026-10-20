using Hellcat.Sim;

namespace Hellcat.Game.World
{
    /// <summary>A scene object that contributes static colliders to the soft-body world (PhysX is not used for the car).</summary>
    public interface IStaticGeometrySource
    {
        void AddTo(StaticWorldBuilder builder);
    }
}
